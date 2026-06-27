#!/bin/bash
# provenance-verification — update check (SessionStart)
# Fetches and NOTIFIES when the repo is behind upstream. Never auto-pulls executable
# code (a deliberate supply-chain choice for a provenance tool). Daily-throttled. MIT.

SRC="${BASH_SOURCE[0]}"; HOOK_DIR="$(cd "$(dirname "$SRC")" && pwd)"; PV_HOME="$(cd "$HOOK_DIR/../.." && pwd)"
command -v git >/dev/null 2>&1 || exit 0
[ -d "$PV_HOME/.git" ] || exit 0

STAMP="$PV_HOME/.last-update-check"
NOW="$(date +%s)"
if [ -f "$STAMP" ]; then
  LAST="$(cat "$STAMP" 2>/dev/null || echo 0)"
  [ $((NOW - LAST)) -lt 86400 ] && exit 0   # checked within 24h
fi
echo "$NOW" > "$STAMP" 2>/dev/null

git -C "$PV_HOME" fetch --quiet 2>/dev/null || exit 0
UP="$(git -C "$PV_HOME" rev-list --count HEAD..@{u} 2>/dev/null || echo 0)"
if [ "${UP:-0}" -gt 0 ] 2>/dev/null; then
  echo "ℹ️ provenance-verification: $UP update(s) available. Run: bash \"$PV_HOME/install.sh\" --update"
fi
exit 0
