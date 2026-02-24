# Claude Code Hooks

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) hooks for sound effects and automatic session notes.

## Sound Hooks

| Event | Trigger | Sound | Vibe |
|---|---|---|---|
| `Notification` | Any notification | `heart-beat.mp3` | Claude needs your attention |
| `Stop` | Response finished | `cinematic-boom.wav` | Claude is done, your turn |
| `TaskCompleted` | Task done | `cash-register.mp3` | Ka-ching — task delivered |

## Session Notes

Automatically captures a summary of every non-trivial Claude Code conversation into `~/Documents/Engineering Notes/`.

On `SessionEnd`, the hook reads the session transcript, calls Bedrock Haiku to summarize and categorize, and writes a markdown note into the appropriate project folder — matching whatever folder structure already exists.

**How it works:**
1. `session-notes-wrapper.sh` captures the hook payload and backgrounds the Python script
2. `session-notes.py` parses the JSONL transcript, skips trivial sessions (< 2 user messages), and calls Bedrock Haiku
3. Haiku returns a structured JSON with folder, filename, and note body
4. The note is written to `<notes_path>/<folder>/<filename>.md`

**Config** (`session-notes.conf.json`):
- `notes_path` — where notes are stored (default: `~/Documents/Engineering Notes`)
- `model_id` — Bedrock model (default: Haiku 4.5 cross-region)
- `min_transcript_messages` — skip sessions shorter than this
- `enabled` — kill switch

**Cost:** ~$0.013 per note (Haiku 4.5).

## Install

```bash
git clone https://github.com/corneliu-iancu/claude-code-hooks.git
cd claude-code-hooks
chmod +x play-sound.sh install.sh session-notes-wrapper.sh
./install.sh
```

The installer merges hooks into `~/.claude/settings.json` without clobbering your existing config.

## Customize

- **Swap sounds** — drop any `.wav` or `.mp3` into `sounds/` and update `settings-template.json`
- **Add events** — see [Claude Code hooks docs](https://docs.anthropic.com/en/docs/claude-code/hooks) for all available events
- **Manual setup** — copy from `settings-template.json` into your settings, replacing `$REPO_DIR` with the absolute path to this repo
- **Disable session notes** — set `"enabled": false` in `session-notes.conf.json`

## Requirements

- macOS (`afplay` for sounds)
- `jq` (for the installer)
- `uv` (for session notes — runs Python with inline deps)
- AWS credentials configured for Bedrock access (for session notes)

## Sound Credits

Sample sounds sourced from [Freesound.org](https://freesound.org) under Creative Commons licenses.
