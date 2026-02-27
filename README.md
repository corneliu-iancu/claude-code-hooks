<p align="center">
  <img src="assets/banner.png" alt="Claude Code Configuration" width="100%">
</p>

# Claude Code Configuration

A comprehensive Claude Code project configuration with hooks, skills, agents, and commands. Includes automatic session notes tracking with sound effects.

## What This Is

This is a **per-project template** for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration. Copy the `.claude/` directory into your project to get:

- **Session Notes Hook** - Automatically captures conversation summaries to `~/Documents/Engineering Notes/`
- **Sound Notifications** - Audio feedback for key events (notifications, task completion, response finished)
- **Organized Structure** - Ready-to-use directories for skills, agents, commands, and hooks
- **Best Practices** - Follows the [ChrisWiles/claude-code-showcase](https://github.com/ChrisWiles/claude-code-showcase) pattern

## Directory Structure

```
your-project/
├── .claude/
│   ├── settings.json           # Hooks, environment, permissions
│   ├── settings.local.json     # Personal overrides (gitignored)
│   ├── .gitignore              # Ignores local files
│   │
│   ├── agents/                 # AI assistants
│   │   └── README.md
│   │
│   ├── commands/               # Slash commands (/command-name)
│   │   └── README.md
│   │
│   ├── hooks/                  # Hook scripts
│   │   ├── README.md
│   │   ├── session-notes-wrapper.sh
│   │   ├── session-notes.py
│   │   └── session-notes.conf.json
│   │
│   ├── skills/                 # Domain knowledge
│   │   └── README.md
│   │
│   └── rules/                  # Modular instructions
│       └── README.md
│
└── sounds/                     # Sound files for hooks
    ├── heart-beat.mp3
    ├── cinematic-boom.wav
    └── cash-register.mp3
```

## Quick Start

### 1. Copy to Your Project

```bash
cd ~/your-project
git clone https://github.com/corneliu-iancu/claude-code-config.git /tmp/claude-config
cp -r /tmp/claude-config/.claude .
cp -r /tmp/claude-config/sounds .
git add .claude/ sounds/
```

### 2. Review Configuration

- `.claude/settings.json` - Hook configuration
- `.claude/hooks/session-notes.conf.json` - Session notes settings

### 3. Commit to Your Repo

```bash
git commit -m "Add Claude Code configuration"
```

Now your team shares the same Claude Code setup!

## Features

### Session Notes Hook

Automatically captures conversation summaries after each session:

**How it works:**
1. `session-notes-wrapper.sh` captures the hook payload and backgrounds the Python script
2. `session-notes.py` parses the JSONL transcript, skips trivial sessions (< 2 user messages), and calls Bedrock Haiku
3. Haiku returns structured JSON with folder, filename, and note body
4. The note is written to `<notes_path>/<folder>/<filename>.md`

**Configuration** (`.claude/hooks/session-notes.conf.json`):
- `notes_path` - Where notes are stored (default: `~/Documents/Engineering Notes`)
- `model_id` - Bedrock model (default: Haiku 4.5 cross-region)
- `min_transcript_messages` - Skip sessions shorter than this
- `enabled` - Kill switch

**Cost:** ~$0.013 per note (Haiku 4.5)

### Sound Notifications

| Event | Trigger | Sound | Vibe |
|-------|---------|-------|------|
| `Notification` | Any notification | `heart-beat.mp3` | Claude needs attention |
| `Stop` | Response finished | `cinematic-boom.wav` | Claude is done |
| `TaskCompleted` | Task done | `cash-register.mp3` | Ka-ching |

## Configuration Reference

### settings.json

Main configuration file defining:
- **Hooks** - PreToolUse, PostToolUse, UserPromptSubmit, Stop
- **Environment variables**
- **Permissions**
- **Enabled plugins**

### settings.local.json (gitignored)

Personal overrides for local development. Never committed to git.

Use this for:
- Disabling sounds locally
- Personal MCP servers
- Machine-specific paths

## Adding Skills, Agents, Commands

Each directory has a README.md explaining the format:

- `.claude/skills/README.md` - Domain knowledge documents
- `.claude/agents/README.md` - AI assistants with focused purposes
- `.claude/commands/README.md` - Slash commands
- `.claude/rules/README.md` - Modular instructions

## Requirements

**For session notes:**
- `uv` - Python package manager (runs with inline dependencies)
- AWS credentials configured for Bedrock access

**For sound effects:**
- macOS (`afplay` for audio playback)

**For installation:**
- `jq` - JSON processor

## Customization

### Swap Sounds

Drop any `.wav` or `.mp3` into `sounds/` and update `settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "afplay \"$CLAUDE_PROJECT_DIR\"/sounds/your-sound.wav &"
          }
        ]
      }
    ]
  }
}
```

### Disable Session Notes

Set `"enabled": false` in `.claude/hooks/session-notes.conf.json`

### Add More Hooks

See [Claude Code hooks documentation](https://docs.anthropic.com/en/docs/claude-code/hooks) for all available events.

## Learn More

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [ChrisWiles/claude-code-showcase](https://github.com/ChrisWiles/claude-code-showcase) - Comprehensive example
- [Claude Code Action](https://github.com/anthropics/claude-code-action) - GitHub Action

## Sound Credits

Sample sounds sourced from [Freesound.org](https://freesound.org) under Creative Commons licenses.

## License

MIT - Use this as a template for your own projects.
