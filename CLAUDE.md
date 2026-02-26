# Claude Code Configuration Template

## What This Is

A reusable Claude Code configuration template with automatic session notes tracking and sound notifications.

## Quick Facts

- **Purpose**: Per-project Claude Code configuration
- **Hooks**: Session notes (PostToolUse), Sound notifications (Stop, Notification, TaskCompleted)
- **Requirements**: macOS, `uv`, AWS Bedrock access

## Structure

```
.claude/
├── settings.json        # Main configuration
├── agents/              # AI assistants (empty template)
├── commands/            # Slash commands (empty template)  
├── hooks/               # Hook scripts
│   ├── session-notes-wrapper.sh
│   ├── session-notes.py
│   └── session-notes.conf.json
├── skills/              # Domain knowledge (empty template)
└── rules/               # Modular instructions (empty template)
```

## Key Files

### `.claude/settings.json`
Configures the PostToolUse hook for automatic session notes.

### `.claude/hooks/session-notes.conf.json`
- `notes_path` - Where notes are saved
- `enabled` - Turn on/off
- `min_transcript_messages` - Skip trivial sessions

## Usage

Copy `.claude/` directory into your project and customize for your needs.
