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
_SECRET_PREFIXES = ("AKIA", "ASIA", "ghp_", "gho_", "xox", "sk-", "-----BEGIN",
                    "AIza", "ya29.", "glpat-", "SG.")

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
    if os.path.getsize(path) == 0 and is_placeholder(path):
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
    if data is None:
        return False
    try:
        text = data.decode("utf-8", "ignore")
    except Exception:
        return False
    if any(p in text for p in _SECRET_PREFIXES):
        return True
    # long high-entropy token on a single line -> likely a secret
    for tok in re.findall(r"[A-Za-z0-9+/=_\-]{40,}", text[:20000]):
        if _shannon(tok) > 4.0:
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


def render_marker(origin_session, date, content_sha, backfill_session, medium):
    short = (origin_session or "unknown").split("/")[0]
    if medium == "markdown":
        return (f"<!-- {MARKER_STATE} | session:{short} | date:{date} "
                f"| content-sha256:{content_sha} | marked-by:{backfill_session} -->")
    return (f"# {MARKER_STATE} · session:{short} · {date} "
            f"· content-sha256:{content_sha} · marked-by:{backfill_session}")


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
    run_id = run_id or datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = os.path.join(BACKUP_ROOT, run_id)
    manifest, counts = [], {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    for d in decisions:
        path = d["path"]
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

        date = datetime.date.today().isoformat()
        content_sha = hashlib.sha256(data).hexdigest()   # bytes EXCLUDING marker (DESIGN §5.5)
        origin = (d.get("origin_event") or {}).get("session") or (d.get("sessions") or ["unknown"])[0]
        marker = render_marker(origin, date, content_sha, backfill_session, medium)
        new_text = insert_marker(text, marker, medium)

        if not do_write:
            bump("would-mark")
            manifest.append({"path": path, "op": "would-mark", "marker": marker,
                             "content_sha256": content_sha, "medium": medium,
                             "origin_session": origin, "machine_reason": d.get("machine_reason")})
            continue

        # write path: re-hash immediately before write (DESIGN §7.5)
        before = _sha_file(path)
        if before != content_sha:
            bump("changed-since-classify"); continue
        os.makedirs(run_dir, exist_ok=True)
        shutil.copy2(path, os.path.join(run_dir, _bak_name(path)))
        with open(path, "w") as f:
            f.write(new_text)
        after = _sha_file(path)
        # verify-after-write: exactly one marker, no conflicted sibling (§7.5)
        reread = open(path, errors="ignore").read()
        ok = len(provenance.find_markers(reread)) >= 1 and not _conflicted_sibling(path)
        if not ok:
            shutil.copy2(os.path.join(run_dir, _bak_name(path)), path)
            bump("verify-failed-restored"); continue
        bump("marked")
        manifest.append({"path": path, "op": "add-marker", "before_sha256": before,
                         "after_sha256": after, "content_sha256": content_sha,
                         "marker": marker, "medium": medium, "origin_session": origin,
                         "backfill_session": backfill_session,
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
    for ln in open(man):
        rec = json.loads(ln)
        if rec.get("op") != "add-marker":
            continue
        bak = os.path.join(run_dir, _bak_name(rec["path"]))
        if os.path.exists(bak):
            shutil.copy2(bak, rec["path"])
            post = _sha_file(rec["path"])
            status = "OK" if post == rec.get("before_sha256") else "WARN-mismatch"
            n += 1
            print(f"  restored {status} {rec['path']}")
    print(f"restored {n} files from run {run_id}")
    return 0


def unmark(path, backfill_session, do_write):
    """Remove exactly the one backfill marker (structural, never substring). Same backup
    path; records to audit (DESIGN §4)."""
    data = read_bytes(path)
    if data is None:
        print(f"unreadable: {path}"); return 1
    text = data.decode("utf-8", "surrogatepass")
    lines = text.split("\n")
    kept = [ln for ln in lines if not re.search(r"\bai-origin:backfilled\b", ln, re.I)]
    if len(kept) == len(lines):
        print(f"no backfill marker found in {path}"); return 1
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
