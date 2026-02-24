# Claude Code Sound Hooks

Sound effects for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) lifecycle events. Makes coding more tactile.

## Sound Map

| Event | Trigger | Sound | Vibe |
|---|---|---|---|
| `Notification` | Any notification | `heart-beat.mp3` | Claude needs your attention |
| `Stop` | Response finished | `cinematic-boom.wav` | Claude is done, your turn |
| `TaskCompleted` | Task done | `cash-register.mp3` | Ka-ching — task delivered |

## Install

```bash
git clone https://github.com/corneliu-iancu/claude-code-hooks.git
cd claude-code-hooks
chmod +x play-sound.sh install.sh
./install.sh
```

The installer merges hooks into `~/.claude/settings.json` without clobbering your existing config.

## Customize

- **Swap sounds** — drop any `.wav` or `.mp3` into `sounds/` and update `settings-template.json`
- **Add events** — see [Claude Code hooks docs](https://docs.anthropic.com/en/docs/claude-code/hooks) for all available events
- **Manual setup** — copy from `settings-template.json` into your settings, replacing `$REPO_DIR` with the absolute path to this repo

## Requirements

- macOS (`afplay`)
- `jq` (for the installer)

## Sound Credits

Sample sounds sourced from [Freesound.org](https://freesound.org) under Creative Commons licenses.
