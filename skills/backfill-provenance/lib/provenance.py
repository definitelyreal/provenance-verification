#!/usr/bin/env python3
# ai-processed:unverified · session:6ab1c2ae-25dd-40bf-9ca2-05072ee58b83 · 2026-06-28
# VENDORED grammar for backfill-provenance v2 (DESIGN.md §0: "vendor, don't gate").
# This is reference/provenance.py + a GRAMMAR_VERSION + recognition of the backfill-only
# `ai-origin:backfilled` state (DESIGN §4, open-q #1). It is the ONE place the backfill
# skill recognizes / renders markers, so detection can never drift from the recognizer.
# Stdlib only. Canonical form: <type>:<status>  e.g. ai-suggestion:unverified
#
# GRAMMAR_VERSION bumps whenever the recognized vocabulary or emission shape changes,
# so two tools can never write markers claiming the same version with different semantics
# (DESIGN §0 grammar-drift guard checks a sha of this module against any trust-kernel copy).

import hashlib
import os
import re
import sys

GRAMMAR_VERSION = "2.0.0-backfill"

# --- canonical vocabulary -------------------------------------------------
# `ai-origin` is a backfill-only TYPE: it asserts "AI authored these bytes per recovered
# evidence" and is creation-only (DESIGN §4). It is intentionally distinct from
# `ai-suggestion`/`ai-processed`, and from `:unverified` (which would imply "no human has
# confirmed" — a claim backfill cannot make about a read/endorse).
TYPES = ("ai-origin", "ai-suggestion", "ai-processed", "human")
STATUSES = ("backfilled", "unverified", "verified", "disputed", "stale")
LEGACY_HIGHLIGHTS = ("#4dff4d", "#feb4dc")  # green, pink — both rewritten to canonical
CANON_HIGHLIGHT = "#e3dfec"    # light purple = AI, unverified

# --- detection ------------------------------------------------------------
# Backfill state: ai-origin:backfilled
_BACKFILL = re.compile(r"\bai-origin:backfilled\b", re.I)
# Canonical status form: ai-suggestion:unverified / ai-processed:verified michael 2026-06-25
_CANON = re.compile(r"\bai-(?:suggestion|processed):(?:unverified|verified|disputed|stale)\b", re.I)
# Legacy global colon form: ai:suggestion / ai:processed / ai:verified
_LEGACY_COLON = re.compile(r"\bai:(?:suggestion|processed|verified)\b", re.I)
# Bare hyphen type with no status (older RG): ai-suggestion / ai-processed / ai-generated
_BARE_HYPHEN = re.compile(r"\bai-(?:suggestion|processed|generated)\b", re.I)
# legacy explicit pre-system marker
_LEGACY_PRE = re.compile(r"\blegacy:pre-system\b", re.I)

_ANY = (_BACKFILL, _CANON, _LEGACY_COLON, _BARE_HYPHEN, _LEGACY_PRE)


def is_marked(text: str) -> bool:
    """True if ANY recognized marker (canonical, backfill, or legacy) is present.
    Transition-period parser: accepts every historical form so a spec-compliant file is
    never falsely re-marked."""
    return any(p.search(text) for p in _ANY)


def find_markers(text: str):
    """Return list of (raw_marker, form)."""
    out = []
    for raw in _BACKFILL.findall(text):
        out.append((raw, "backfill"))
    for raw in _CANON.findall(text):
        out.append((raw, "canonical"))
    for raw in _LEGACY_COLON.findall(text):
        out.append((raw, "legacy-colon"))
    for raw in _BARE_HYPHEN.findall(text):
        out.append((raw, "bare-hyphen"))
    for raw in _LEGACY_PRE.findall(text):
        out.append((raw, "legacy-pre"))
    return out


# --- normalization (legacy -> canonical) ----------------------------------
def normalize(marker: str) -> str:
    m = marker.strip().lower()
    if _BACKFILL.fullmatch(m):
        return "ai-origin:backfilled"
    if _CANON.fullmatch(m):
        return m
    if m == "ai:suggestion":
        return "ai-suggestion:unverified"
    if m == "ai:processed":
        return "ai-processed:unverified"
    if m == "ai:verified":
        return "ai-processed:verified"
    if m in ("ai-suggestion", "ai-generated"):
        return "ai-suggestion:unverified"
    if m == "ai-processed":
        return "ai-processed:unverified"
    if m == "legacy:pre-system":
        return "ai-suggestion:unverified"
    return m


def grammar_sha() -> str:
    """sha256 of this module's source — the DESIGN §0 drift check compares this against any
    other copy (trust-kernel) claiming the same GRAMMAR_VERSION."""
    try:
        with open(os.path.abspath(__file__), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


# --- soft .ai infix resolution -------------------------------------------
def variants(path):
    d, b = os.path.split(path)
    if ".ai." in b:
        other = b.replace(".ai.", ".", 1)
    else:
        root, ext = os.path.splitext(b)
        other = root + ".ai" + ext
    return [path, os.path.join(d, other)]


def resolve(path):
    for p in variants(path):
        if os.path.exists(p):
            return p
    return path


# --- CLI ------------------------------------------------------------------
def _main(argv):
    if len(argv) >= 2 and argv[1] == "check":
        try:
            with open(argv[2], "r", errors="ignore") as f:
                text = f.read()
        except OSError:
            return 0
        if is_marked(text):
            return 0
        print(f"unmarked: {argv[2]}")
        return 1
    if len(argv) >= 2 and argv[1] == "normalize":
        print(normalize(argv[2] if len(argv) > 2 else sys.stdin.read().strip()))
        return 0
    if len(argv) >= 2 and argv[1] == "version":
        print(f"{GRAMMAR_VERSION} {grammar_sha()[:16]}")
        return 0
    print("usage: provenance.py {check <file> | normalize <marker> | version}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
