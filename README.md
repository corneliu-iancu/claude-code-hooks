<p align="center">
  <img src="assets/banner.png" alt="Claude Code Configuration" width="100%">
</p>

# Claude Code Config

Global [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration — sound effects + automatic session notes.

## What's Included

### Sound Notifications

Hooks installed into `~/.claude/settings.json` that play sounds via `afplay`:

| Event | Sound | Vibe |
|-------|-------|------|
| `Notification` | `heart-beat.mp3` | Claude needs attention |
| `Stop` | `cinematic-boom.wav` | Response finished |
| `TaskCompleted` | `cash-register.mp3` | Ka-ching |

### Session Notes

On `SessionEnd`, a background script summarizes the conversation transcript using AWS Bedrock and writes a markdown note to `~/Documents/LLM Engineering Notes/`. Trivial sessions (fewer than 4 user messages) are skipped.

## Install

```bash
git clone https://github.com/corneliu-iancu/claude-code-config.git
cd claude-code-config
./install.sh
```

`install.sh` deep-merges the hook definitions into your existing `~/.claude/settings.json` using `jq`. Sound commands and session-notes scripts reference this repo by absolute path, so don't move it after installing.

## Repo Structure

```
claude-code-config/
├── install.sh                  # Merges hooks into ~/.claude/settings.json
├── settings-template.json      # Hook definitions (reference copy)
├── play-sound.sh               # afplay wrapper (never blocks, never fails)
├── sounds/
│   ├── heart-beat.mp3
│   ├── cinematic-boom.wav
│   └── cash-register.mp3
├── .claude/
│   └── hooks/
│       ├── session-notes-wrapper.sh   # Captures stdin, backgrounds Python
│       ├── session-notes.py           # Parses transcript, calls Bedrock
│       └── session-notes.conf.json    # Session notes configuration
├── assets/
│   └── banner.png
├── CLAUDE.md
└── README.md
```

## Configuration

Session notes are configured in `.claude/hooks/session-notes.conf.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `notes_path` | `~/Documents/LLM Engineering Notes` | Where notes are written |
| `model` | `haiku` | Model name (`haiku`, `sonnet`, or a full model ID) |
| `provider` | `auto` | `auto`, `anthropic`, or `bedrock` |
| `aws_region` | `us-west-2` | AWS region (only used when provider is `bedrock`) |
| `min_transcript_messages` | `4` | Skip sessions shorter than this |
| `max_transcript_chars` | `120000` | Truncate long transcripts |
| `enabled` | `true` | Kill switch |

Provider auto-detection checks for `ANTHROPIC_API_KEY` first, then `AWS_BEARER_TOKEN_BEDROCK`.

## Customization

**Swap sounds** — Drop any `.wav`/`.mp3` into `sounds/` and update the hook commands in `~/.claude/settings.json`.

**Disable session notes** — Set `"enabled": false` in `.claude/hooks/session-notes.conf.json`.

## Requirements

- **macOS** — sounds use `afplay`
- **`jq`** — used by `install.sh` to merge JSON (`brew install jq`)
- **Anthropic API key or AWS Bedrock credentials** — for session notes summarization

## License

MIT
