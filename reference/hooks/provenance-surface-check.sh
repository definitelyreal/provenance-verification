#!/bin/bash
# provenance-verification — surface check (PostToolUse)
# Reminds you to mark AI content pasted into external surfaces (Sheets / Docs / Slack /
# clipboard) with the canonical form. Warn-only. MIT.

INPUT=""; [ -t 0 ] || INPUT="$(cat)"
if [ -z "${TOOL_NAME:-}" ] && [ -n "$INPUT" ]; then
  TOOL_NAME="$(printf '%s' "$INPUT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)"
  TOOL_INPUT="$(printf '%s' "$INPUT" | python3 -c "import sys,json,json as j;print(j.dumps(json.load(sys.stdin).get('tool_input',{})))" 2>/dev/null)"
fi

case "${TOOL_NAME:-}" in
  Bash)
    CMD="$(printf '%s' "${TOOL_INPUT:-}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('command',''))" 2>/dev/null)"
    if printf '%s' "$CMD" | grep -qE "pbcopy|osascript.*(paste|keystroke)"; then
      echo "⚠️ provenance-verification: clipboard/paste detected."
      echo "   → Pasting AI content into a Doc/Slack/Notion? Prepend '<!-- ai-suggestion:unverified -->' and highlight #e3dfec."
    fi ;;
  mcp__google-sheets__update_cells|mcp__google-sheets__add_rows|mcp__google-sheets__batch_update_cells|mcp__google-sheets__batch_update|mcp__google-sheets__add_columns)
    echo "⚠️ provenance-verification: Google Sheets write detected."
    echo "   → Populate the :Provenance column with 'ai-suggestion:unverified {YYYY-MM-DD} {short-id}' (or ai-processed:unverified); highlight touched cells #e3dfec." ;;
esac
exit 0
