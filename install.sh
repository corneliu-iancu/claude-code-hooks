#!/usr/bin/env bash
# Merges Claude Code sound hooks into ~/.claude/settings.json (non-destructive).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required. Install with: brew install jq"
  exit 1
fi

if [ ! -f "$SETTINGS" ]; then
  echo "Error: $SETTINGS not found. Run Claude Code at least once first."
  exit 1
fi

HOOKS=$(cat <<EOF
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$REPO_DIR/play-sound.sh heart-beat.mp3"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$REPO_DIR/play-sound.sh cinematic-boom.wav"
          }
        ]
      }
    ],
    "TaskCompleted": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$REPO_DIR/play-sound.sh cash-register.mp3"
          }
        ]
      }
    ]
  }
}
EOF
)

# Deep-merge hooks into existing settings
jq -s '.[0] * .[1]' "$SETTINGS" <(echo "$HOOKS") > "$SETTINGS.tmp" \
  && mv "$SETTINGS.tmp" "$SETTINGS"

echo "Sound hooks installed into $SETTINGS"
echo "Repo: $REPO_DIR"
