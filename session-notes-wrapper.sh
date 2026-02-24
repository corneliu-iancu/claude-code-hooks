#!/usr/bin/env bash
# Wrapper for session-notes.py — captures stdin before pipe closes, backgrounds Python.
# Always exits 0 so it never blocks Claude Code shutdown.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/.claude/session-notes.log"

PAYLOAD="$(cat)"

echo "$PAYLOAD" | nohup python3 "$SCRIPT_DIR/session-notes.py" >> "$LOG" 2>&1 &

exit 0
