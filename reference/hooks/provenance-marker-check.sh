#!/bin/bash
# provenance-verification — marker check (PostToolUse: Write)
# Warns when an AI-written markdown file lacks a provenance marker, but ONLY for paths
# the user opted into via user.local (enforce_paths). No config => silent no-op, so it
# does nothing weird out of the box. MIT.

SRC="${BASH_SOURCE[0]}"; HOOK_DIR="$(cd "$(dirname "$SRC")" && pwd)"; PV_HOME="$(cd "$HOOK_DIR/../.." && pwd)"
USER_CFG="$PV_HOME/claude/user.local.md"

# Tool data may arrive via env (TOOL_NAME/TOOL_INPUT) or stdin JSON.
INPUT=""; [ -t 0 ] || INPUT="$(cat)"
if [ -z "${TOOL_NAME:-}" ] && [ -n "$INPUT" ]; then
  TOOL_NAME="$(printf '%s' "$INPUT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)"
  FILE_PATH="$(printf '%s' "$INPUT" | python3 -c "import sys,json;print((json.load(sys.stdin).get('tool_input',{}) or {}).get('file_path',''))" 2>/dev/null)"
else
  FILE_PATH="$(printf '%s' "${TOOL_INPUT:-}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null)"
fi

[ "${TOOL_NAME:-}" = "Write" ] || exit 0
case "$FILE_PATH" in *.md) ;; *) exit 0 ;; esac
case "$FILE_PATH" in *.ai.md) exit 0 ;; esac
BASE="$(basename "$FILE_PATH")"
case "$BASE" in CLAUDE.md|CLAUDE.*.md|README.md|MEMORY.md|LICENSE*|CHANGELOG.md|VERSION|*.local.md|SCRATCHPAD.md|INTENT.md|STATE.md) exit 0 ;; esac

# Only enforce on user-opted paths. No config or no enforce_paths => silent.
[ -f "$USER_CFG" ] || exit 0
GLOBS="$(python3 - "$USER_CFG" <<'PY' 2>/dev/null
import sys,re
t=open(sys.argv[1]).read()
m=re.search(r'enforce_paths:\s*\[(.*?)\]',t,re.S)
print(m.group(1) if m else '')
PY
)"
[ -n "$GLOBS" ] || exit 0

MATCH=0
IFS=',' read -ra G <<< "$GLOBS"
for g in "${G[@]}"; do
  g="$(printf '%s' "$g" | sed -e 's/^[[:space:]"]*//' -e 's/[[:space:]"]*$//')"; g="${g/#\~/$HOME}"; [ -z "$g" ] && continue
  pre="${g%%\**}"   # literal prefix before first wildcard
  case "$FILE_PATH" in "$pre"*) MATCH=1; break ;; esac
done
[ "$MATCH" = "1" ] || exit 0

# Detect a marker via the canonical recognizer (accepts legacy forms too).
if [ -f "$FILE_PATH" ] && python3 "$PV_HOME/reference/provenance.py" check "$FILE_PATH" >/dev/null 2>&1; then
  exit 0
fi
echo "⚠️ provenance-verification: '$BASE' lacks a provenance marker."
echo "   → Use a .ai.md extension, or add frontmatter: <!-- ai-suggestion:unverified | session: <id> | date: $(date +%Y-%m-%d) -->"
echo "   → If this file is human-written, ignore this."
exit 0
