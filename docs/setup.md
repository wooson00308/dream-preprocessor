# Setup Guide

Detailed installation and configuration for dream-preprocessor.

## 1. Clone & Install

```bash
git clone https://github.com/wooson00308/dream-preprocessor.git
cd dream-preprocessor
pip3 install -e .
```

Verify:

```bash
dream-prep list
dream-heartbeat --help
```

## 2. Register /dream Skill

Copy the skill file included in the repo:

```bash
mkdir -p ~/.claude/skills/dream
cp skill/SKILL.md ~/.claude/skills/dream/SKILL.md
```

See [`skill/SKILL.md`](../skill/SKILL.md) for the full skill definition. Customize as needed.

## 3. Write HEARTBEAT.md

Register jobs in `~/.claude/HEARTBEAT.md`.
The project slug is the directory name under `~/.claude/projects/` (e.g. `-Users-yourname`).

```markdown
# HEARTBEAT

## dream-home
- slug: -Users-yourname
- prompt: /dream
- interval: 3h
- timeout: 10m
- condition: dream-prep status --slug="-Users-yourname" | grep -q "미처리: 0" && exit 1 || exit 0
```

Add more `## job-name` blocks to register additional jobs.

## 4. Manual Test

Test before setting up automation:

```bash
# Preprocess only
dream-prep prep --slug="-Users-yourname" -n 3

# Run all jobs once (Claude wakes up and runs /dream)
dream-heartbeat once
```

## 5. Register with launchd

Find the actual path of dream-heartbeat:

```bash
which dream-heartbeat
# e.g. /Users/yourname/.pyenv/versions/3.11.9/bin/dream-heartbeat
```

Create the plist:

```bash
cat > ~/Library/LaunchAgents/com.dream-heartbeat.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dream-heartbeat</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/yourname/.pyenv/versions/3.11.9/bin/dream-heartbeat</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/yourname/.claude/dream-heartbeat/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yourname/.claude/dream-heartbeat/launchd_stderr.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/yourname</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/Users/yourname/.pyenv/versions/3.11.9/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/yourname</string>
    </dict>
</dict>
</plist>
EOF
```

> Replace `/Users/yourname` and the Python path with your actual paths.
> PATH must include the directory containing the `claude` CLI (usually `/opt/homebrew/bin`).

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/com.dream-heartbeat.plist
```

Verify:

```bash
dream-heartbeat status
```

Unload:

```bash
launchctl unload ~/Library/LaunchAgents/com.dream-heartbeat.plist
```

> launchd requires `--foreground` mode to work properly.
> With KeepAlive enabled, the process auto-restarts if it dies.

---

## CLI Reference

### dream-prep

Extracts user/assistant text from transcript JSONL and converts to compact markdown.

- Compresses code blocks (3 lines or fewer kept, 4+ lines → first line + ellipsis)
- Merges consecutive tool calls (`[tools: Bash, Read x2]`)
- Strips system messages

```bash
dream-prep list                            # Transcript count per project
dream-prep status --slug="-Users-yourname" # Processing status
dream-prep prep --slug="-Users-yourname" -n 5  # Run preprocessing
```

### dream-heartbeat

Generic scheduler that parses `~/.claude/HEARTBEAT.md` and runs jobs on schedule.

```bash
dream-heartbeat start       # Start daemon (background)
dream-heartbeat start -f    # Foreground mode
dream-heartbeat stop        # Stop daemon
dream-heartbeat status      # Status + recent logs
dream-heartbeat jobs        # List configured jobs
dream-heartbeat once        # Run all jobs once
dream-heartbeat once -j "name"  # Run specific job once
```

### HEARTBEAT.md Format

```markdown
## job-name
- slug: -Users-yourname
- prompt: /dream
- interval: 3h
- timeout: 600
- condition: dream-prep status --slug="-Users-yourname" 2>&1 | grep -q "미처리: [1-9]"
```

| Field | Description | Default |
|-------|-------------|---------|
| slug | Project slug (`~/.claude/projects/` subdirectory name) | Required |
| prompt | Prompt passed to `claude -p` | Required |
| interval | Run interval (s/m/h/d) | 1h |
| timeout | Timeout (s/m/h/d) | 600s |
| condition | Pre-run shell check (exit 0 = run) | None (always run) |

## /dream Skill

This tool handles preprocessing only. The actual consolidation logic runs in the Claude Code `/dream` skill.
See [`skill/SKILL.md`](../skill/SKILL.md) for the full skill definition.

The skill follows KAIROS autoDream's 4 phases:
1. Orient — Survey current memory state
2. Gather — Read preprocessed markdown
3. Consolidate — Merge with existing memory, create/update topic files
4. Prune & Index — Deduplicate, update MEMORY.md index
