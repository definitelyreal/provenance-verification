#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# backfill-provenance v2 / mark.py
# Safety primitives + the only code that mutates files. Backups live OUTSIDE the synced
# tree (DESIGN §7.2). Dropbox placeholders are never read as empty / never auto-hydrated
# (§6). Secrets are quarantined by glob AND content before any byte/hash is persisted (§7.1).
# Marker insertion is structural per-language, detect-only idempotent (§7.3). Restore + unmark
# go through the same backup path (§4, §7.6). DRY-RUN by default. Never writes `verified`.

import datetime
import fnmatch
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import provenance  # vendored grammar

BACKUP_ROOT = os.path.expanduser("~/Library/Application Support/trust-kernel/backfill")
MARKER_STATE = "ai-origin:backfilled"   # DESIGN §4 / open-q #1 — the ONE place it's defined

QUARANTINE_GLOBS = [
    ".env*", "*.pem", "*.key", "*_key", "*secret*", "*token*", "*credential*",
    "auth.json", ".brain-api-token", "id_rsa*", "*.p12", "*.pfx",
]
_SECRET_PREFIXES = ("AKIA", "ASIA", "ghp_", "gho_", "ghs_", "github_pat_", "xox", "sk-",
                    "-----BEGIN", "AIza", "ya29.", "glpat-", "SG.", "AAAA", "hooks.slack.com")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}")
# secret-ish assignment: KEY = "<40+ high-entropy>" (avoids bare commit-hash / checksum false positives)
_ASSIGN_SECRET = re.compile(
    r"(?i)(?:secret|token|password|passwd|api[_-]?key|access[_-]?key|private[_-]?key)\s*[:=]\s*"
    r"['\"]?([A-Za-z0-9+/=_\-]{16,})")

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".rb", ".go", ".rs", ".java",
            ".c", ".cpp", ".h", ".css", ".scss", ".sql", ".yaml", ".yml", ".toml"}


# --- Dropbox placeholder guard (DESIGN §6) --------------------------------
def is_placeholder(path):
    try:
        out = subprocess.run(["xattr", path], capture_output=True, text=True, timeout=5)
        if "com.dropbox.placeholder" in out.stdout:
            return True
    except Exception:
        pass
    return False


def read_bytes(path, placeholder_sink=None, max_bytes=8 * 1024 * 1024):
    """Read on-disk bytes, or None if missing / placeholder / too large. A placeholder is
    recorded (never read as empty, never hydrated)."""
    if not os.path.exists(path):
        return None
    if is_placeholder(path):   # unconditional: a nonzero placeholder is still not real bytes
        if placeholder_sink is not None:
            placeholder_sink.add(path)
        return None
    try:
        if os.path.getsize(path) > max_bytes:
            return None
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def snap_bytes(snapshot_file, max_bytes=8 * 1024 * 1024):
    try:
        if os.path.getsize(snapshot_file) > max_bytes:
            return None
        with open(snapshot_file, "rb") as f:
            return f.read()
    except OSError:
        return None


# --- secret quarantine (DESIGN §7.1) --------------------------------------
def _shannon(s):
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def quarantined_by_glob(path):
    b = os.path.basename(path)
    return any(fnmatch.fnmatch(b, g) for g in QUARANTINE_GLOBS)


def quarantined_by_content(data):
    """True if the file looks like it holds a secret. Conservative toward SKIPPING such a
    file (never mutate a credential). Scans the WHOLE file. Targets real secret shapes
    (known prefixes, JWTs, secret-named assignments) rather than bare hex/base64 tokens,
    which would false-positive on commit hashes / checksums in ordinary docs."""
    if data is None:
        return False
    try:
        text = data.decode("utf-8", "ignore")
    except Exception:
        return False
    if any(p in text for p in _SECRET_PREFIXES):
        return True
    if _JWT.search(text):
        return True
    for m in _ASSIGN_SECRET.finditer(text):
        if _shannon(m.group(1)) > 3.0:
            return True
    return False


# --- marker rendering + structural insertion (DESIGN §5, §7.3) ------------
def medium_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md":
        return "markdown"
    if ext in CODE_EXT:
        return "code"
    return "other"


def render_marker(origin_session, date, content_sha, backfill_session, medium, confidence="high"):
    short = (origin_session or "unknown").split("/")[0]
    if medium == "markdown":
        return (f"<!-- {MARKER_STATE} | session:{short} | date:{date} "
                f"| confidence:{confidence} | content-sha256:{content_sha} | marked-by:{backfill_session} -->")
    return (f"# {MARKER_STATE} · session:{short} · {date} "
            f"· confidence:{confidence} · content-sha256:{content_sha} · marked-by:{backfill_session}")


_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_CODING = re.compile(r"^#.*coding[:=]")


def insert_marker(text, marker, medium):
    """Insert structurally: after a code shebang/encoding line, or after markdown YAML
    frontmatter; else at the very top. Returns new text."""
    if medium == "code":
        lines = text.split("\n")
        idx = 0
        if lines and lines[0].startswith("#!"):
            idx = 1
        if idx < len(lines) and _CODING.match(lines[idx]):
            idx += 1
        lines.insert(idx, marker)
        return "\n".join(lines)
    # markdown
    m = _FRONTMATTER.match(text)
    if m:
        return text[:m.end()] + marker + "\n" + text[m.end():]
    return marker + "\n" + text


# --- mutation with backup + verify (DESIGN §7.2, §7.5, §7.6) --------------
def _bak_name(path):
    return hashlib.sha256(path.encode()).hexdigest() + os.path.splitext(path)[1]


def _sha_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _conflicted_sibling(path):
    d, b = os.path.split(path)
    root, ext = os.path.splitext(b)
    pattern = f"{root} (*conflicted copy*){ext}"
    try:
        return any(fnmatch.fnmatch(x, pattern) for x in os.listdir(d or "."))
    except OSError:
        return False


def apply_markers(decisions, backfill_session, do_write, run_id=None):
    """decisions: list of classification dicts with action=='mark' chosen for application.
    Returns (manifest, counts). do_write False => dry-run (no bytes touched)."""
    # run_id carries a random suffix so a second apply in the same second can never overwrite
    # a prior run's backups/manifest (DESIGN §7.2).
    run_id = run_id or (datetime.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3))
    run_dir = os.path.join(BACKUP_ROOT, run_id)
    if do_write and os.path.exists(os.path.join(run_dir, "changes.jsonl")):
        raise RuntimeError(f"run_id {run_id} already has a manifest — refusing to overwrite")
    manifest, counts = [], {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    for d in decisions:
        path = d["path"]
        # never write through a link: a symlink (final or parent) or a hardlinked file would
        # mutate an out-of-scope target that restore cannot fully undo.
        if os.path.islink(path) or os.path.realpath(path) != os.path.abspath(path):
            bump("skip-symlink"); continue
        try:
            if os.lstat(path).st_nlink > 1:
                bump("skip-hardlink"); continue
        except OSError:
            bump("unreadable"); continue
        medium = medium_of(path)
        if medium == "other":
            bump("skip-unsupported"); continue
        if quarantined_by_glob(path):
            bump("quarantined-glob"); continue
        data = read_bytes(path)
        if data is None:
            bump("unreadable"); continue
        if quarantined_by_content(data):
            bump("quarantined-content"); continue
        text = data.decode("utf-8", "surrogatepass")
        if provenance.is_marked(text):
            bump("already-marked"); continue

        cur_sha = hashlib.sha256(data).hexdigest()   # bytes EXCLUDING marker (DESIGN §5.5)
        expected = d.get("content_sha")              # report-time disk sha (write-race guard)
        if expected and cur_sha != expected:
            bump("changed-since-classify"); continue
        date = datetime.date.today().isoformat()
        confidence = d.get("confidence") or "high"
        origin = (d.get("origin_event") or {}).get("session") or (d.get("sessions") or ["unknown"])[0]
        marker = render_marker(origin, date, cur_sha, backfill_session, medium, confidence)
        new_text = insert_marker(text, marker, medium)

        if not do_write:
            bump("would-mark")
            manifest.append({"path": path, "op": "would-mark", "marker": marker,
                             "content_sha256": cur_sha, "medium": medium, "confidence": confidence,
                             "origin_session": origin, "machine_reason": d.get("machine_reason")})
            continue

        # write path: re-hash immediately before write to catch a TOCTOU change since our read
        before = _sha_file(path)
        if before != cur_sha:
            bump("changed-since-classify"); continue
        os.makedirs(run_dir, exist_ok=True)
        shutil.copy2(path, os.path.join(run_dir, _bak_name(path)))
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(fd, "w") as f:
            f.write(new_text)
        after = _sha_file(path)
        # verify-after-write: EXACTLY ONE backfill marker, no conflicted sibling (§7.5)
        reread = open(path, errors="ignore").read()
        n_backfill = len(re.findall(r"ai-origin:backfilled", reread, re.I))
        ok = n_backfill == 1 and not _conflicted_sibling(path)
        if not ok:
            shutil.copy2(os.path.join(run_dir, _bak_name(path)), path)
            bump("verify-failed-restored"); continue
        bump("marked")
        manifest.append({"path": path, "op": "add-marker", "before_sha256": before,
                         "after_sha256": after, "content_sha256": cur_sha,
                         "marker": marker, "medium": medium, "confidence": confidence,
                         "origin_session": origin, "backfill_session": backfill_session,
                         "at": datetime.datetime.now().isoformat()})

    if do_write and manifest:
        os.makedirs(run_dir, exist_ok=True)
        os.chmod(run_dir, 0o700)
        with open(os.path.join(run_dir, "changes.jsonl"), "w") as f:
            for m in manifest:
                f.write(json.dumps(m) + "\n")
    return manifest, counts, run_id


def restore(run_id):
    run_dir = os.path.join(BACKUP_ROOT, run_id)
    man = os.path.join(run_dir, "changes.jsonl")
    if not os.path.exists(man):
        print(f"no manifest for run {run_id} at {run_dir}")
        return 1
    n = 0
    failures = []
    for ln in open(man):
        rec = json.loads(ln)
        if rec.get("op") != "add-marker":
            continue
        path = rec["path"]
        bak = os.path.join(run_dir, _bak_name(path))
        if not os.path.exists(bak):
            failures.append(f"MISSING-BACKUP {path} (still marked)")
            print(f"  FAIL missing-backup {path}")
            continue
        shutil.copy2(bak, path)
        post = _sha_file(path)
        if post == rec.get("before_sha256"):
            n += 1
            print(f"  restored OK {path}")
        else:
            failures.append(f"HASH-MISMATCH {path} (did not return to pre-mark bytes)")
            print(f"  FAIL hash-mismatch {path}")
    print(f"restored {n} files from run {run_id}")
    if failures:
        print(f"RESTORE FAILED for {len(failures)} file(s):")
        for f in failures:
            print(f"  - {f}")
        return 2
    return 0


def unmark(path, backfill_session, do_write):
    """Remove exactly the one backfill marker (structural, never substring). Same backup
    path; records to audit (DESIGN §4)."""
    data = read_bytes(path)
    if data is None:
        print(f"unreadable: {path}"); return 1
    text = data.decode("utf-8", "surrogatepass")
    lines = text.split("\n")
    # structural: remove ONLY a line that is itself a backfill marker comment (md or code),
    # never a line that also carries content.
    struct = re.compile(r"^\s*(?:<!--\s*ai-origin:backfilled\b.*?-->|#\s*ai-origin:backfilled\b.*)\s*$", re.I)
    kept = [ln for ln in lines if not struct.match(ln)]
    if len(kept) == len(lines):
        print(f"no own-line backfill marker found in {path} "
              f"(a marker sharing a line with content is left untouched)"); return 1
    if not do_write:
        print(f"would unmark {path} (removes {len(lines)-len(kept)} marker line(s)) — dry-run")
        return 0
    run_id = "unmark-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = os.path.join(BACKUP_ROOT, run_id)
    os.makedirs(run_dir, exist_ok=True)
    shutil.copy2(path, os.path.join(run_dir, _bak_name(path)))
    with open(path, "w") as f:
        f.write("\n".join(kept))
    reread = open(path, errors="ignore").read()
    remaining = sum(1 for _ in re.finditer(r"\bai-origin:backfilled\b", reread, re.I))
    with open(os.path.join(run_dir, "audit.jsonl"), "w") as f:
        f.write(json.dumps({"op": "unmark", "path": path, "backfill_session": backfill_session,
                            "remaining_backfill_markers": remaining,
                            "at": datetime.datetime.now().isoformat()}) + "\n")
    print(f"unmarked {path} ({remaining} backfill markers remain); backup at {run_dir}")
    return 0 if remaining == 0 else 2
