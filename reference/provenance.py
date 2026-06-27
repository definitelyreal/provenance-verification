#!/usr/bin/env python3
# provenance-verification reference library — the one place provenance markers are recognized,
# normalized, and emitted. Replaces grep-by-hand in scattered hooks so detection
# can never drift again. Dependency-light: stdlib only.
# Canonical form: <type>:<status>  e.g. ai-suggestion:unverified
# See ../spec/SPEC.md.
#
# ai-processed:unverified · session:0f1af029-e60e-421a-9ad7-1fd0f887c8b5 · 2026-06-25

import re
import sys

# --- canonical vocabulary -------------------------------------------------
TYPES = ("ai-suggestion", "ai-processed", "human")
STATUSES = ("unverified", "verified", "disputed", "stale")
LEGACY_HIGHLIGHT = "#4dff4d"   # old RG green
CANON_HIGHLIGHT = "#feb4dc"    # pink = AI, unverified

# --- detection ------------------------------------------------------------
# Canonical status form: ai-suggestion:unverified / ai-processed:verified michael 2026-06-25
_CANON = re.compile(r"\bai-(?:suggestion|processed):(?:unverified|verified|disputed|stale)\b", re.I)
# Legacy global colon form: ai:suggestion / ai:processed / ai:verified
_LEGACY_COLON = re.compile(r"\bai:(?:suggestion|processed|verified)\b", re.I)
# Bare hyphen type with no status (older RG): ai-suggestion / ai-processed / ai-generated
_BARE_HYPHEN = re.compile(r"\bai-(?:suggestion|processed|generated)\b", re.I)
# legacy explicit pre-system marker
_LEGACY_PRE = re.compile(r"\blegacy:pre-system\b", re.I)

_ANY = (_CANON, _LEGACY_COLON, _BARE_HYPHEN, _LEGACY_PRE)


def is_marked(text: str) -> bool:
    """True if ANY recognized marker (canonical or legacy) is present.
    This is the transition-period parser: it must accept every historical form
    so spec-compliant files are never falsely flagged as unmarked."""
    return any(p.search(text) for p in _ANY)


def find_markers(text: str):
    """Return list of (raw_marker, form) found. form in {canonical, legacy-colon, bare-hyphen, legacy-pre}."""
    out = []
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
    """Map any legacy marker spelling to the canonical type:status form.
    Conservative on type when ambiguous: colon `ai:verified` -> ai-processed:verified."""
    m = marker.strip().lower()
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


def canonical_frontmatter(session_id: str, date: str, asof: str | None = None, type_: str = "ai-suggestion") -> str:
    asof_part = f" | asof:{asof}" if asof else ""
    return f"<!-- {type_}:unverified | session:{session_id} | date:{date}{asof_part} -->"


# --- CLI ------------------------------------------------------------------
def _main(argv):
    if len(argv) >= 2 and argv[1] == "check":
        # `provenance.py check <file>`: exit 0 if marked, 1 if not.
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
    print("usage: provenance.py {check <file> | normalize <marker>}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
