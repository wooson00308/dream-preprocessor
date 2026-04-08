# dream-preprocessor

_Sleep well, remember everything._

**[한국어](docs/ko.md)**

---

```
  Transcript        dream-prep         /dream             Memory
  (raw JSONL)       (preprocess)       (consolidate)      (topic files)

  Session 1 ─┐
  Session 2 ─┤
  Session 3 ─┼─────► Markdown ─────► ┌─ Orient ─────────►  MEMORY.md
  Session 4 ─┤       (compact)       │  Gather             user.md
  Session 5 ─┘                       │  Consolidate        feedback.md
                                     └─ Prune              project.md

      L3                                L2                     L1
  (raw logs)                        (knowledge)              (index)
```

---

## The Problem

Claude Code saves every conversation as a transcript JSONL file.
The files pile up. Nobody reads them.

When a new session starts, Claude is a blank slate.
The 4-hour debugging session from yesterday? The architecture decision from last week? Gone.

Claude Code only carries two things across sessions:

| Storage | Auto-loaded | Limitation |
|---------|-------------|------------|
| CLAUDE.md | Entire file | You write and maintain it manually |
| MEMORY.md | First 200 lines only | Topic files require manual Read to access |

Everything is in the transcripts.
The memory system already exists.
The only missing piece is the bridge between them.

## The Solution

Humans experience things during the day and consolidate memories during sleep.
The hippocampus reviews the day's experiences, keeps what matters, and discards the rest.

dream does the same thing for Claude.

It periodically reads transcripts, strips the noise,
and turns them into memories that are ready for the next conversation.

No need to say "remember this." It remembers.
No need to say "organize that." It organizes.

That's why it's called dream.

---

## The Process

### 1. Heartbeat --- Decide whether to wake up

```
[heartbeat daemon]
     │
     ├─ Wakes every 60 seconds
     ├─ Parses job list from HEARTBEAT.md
     ├─ Checks interval per job (e.g. every 3 hours)
     └─ Runs condition check
         └─ "Any unprocessed transcripts?"
              ├─ No  → Skip (zero cost)
              └─ Yes → Next step
```

The daemon itself never calls the LLM. Always-on, zero token cost.
It only wakes Claude when there's work to do.

### 2. dream-prep --- Preprocess

Raw transcript JSONL is too large and noisy to feed directly to an LLM.

dream-prep handles:
- Extract only user/assistant text
- Compress code blocks (4+ lines → first line + ellipsis)
- Merge consecutive tool calls (`[tools: Bash, Read x2]`)
- Strip system messages

Thousands of JSONL lines become a compact, readable markdown.

### 3. /dream --- Consolidate

Claude wakes up and runs the `/dream` skill.
It follows the 4 phases of KAIROS autoDream:

| Phase | Name | Action |
|-------|------|--------|
| 1 | Orient | Survey current memory state |
| 2 | Gather | Read preprocessed markdown |
| 3 | Consolidate | Merge with existing memory, create/update topic files |
| 4 | Prune & Index | Deduplicate, update MEMORY.md index |

### 4. Memory --- Result

After consolidation, memory is up to date.
In the next session, Claude already knows the context.

```
Before dream:
  "What's the project structure?"  ← asked every single session

After dream:
  (Already knows. Starts working immediately.)
```

---

## Memory Layers

```
┌─────────────────────────────────────────┐
│  L1: MEMORY.md                          │
│  Always loaded. 200-line index.         │
├─────────────────────────────────────────┤
│  L2: Topic Files                        │
│  Refined knowledge. Referenced on need. │
│  user.md, feedback.md, project.md ...   │
├─────────────────────────────────────────┤
│  L3: Transcript JSONL                   │
│  Raw conversation logs.                 │
│  Auto-saved. Auto-refined. Zero effort. │
└─────────────────────────────────────────┘
```

---

## Prerequisites

- macOS (launchd-based automation)
- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)

## Quick Start

```bash
git clone https://github.com/wooson00308/dream-preprocessor.git
cd dream-preprocessor
pip3 install -e .

# Register /dream skill
mkdir -p ~/.claude/skills/dream
cp skill/SKILL.md ~/.claude/skills/dream/SKILL.md

# Test
dream-prep list
dream-heartbeat once
```

For full setup including launchd registration, see the [Setup Guide](docs/setup.md).

## Configuration

Register jobs in `~/.claude/HEARTBEAT.md`:

```markdown
## my-project
- slug: -Users-yourname-Git-myproject
- prompt: /dream
- interval: 3h
- timeout: 10m
- condition: dream-prep status --slug="..." | grep -q "미처리: 0" && exit 1 || exit 0
```

| Field | Description | Default |
|-------|-------------|---------|
| slug | Project slug (`~/.claude/projects/` subdirectory name) | Required |
| prompt | Prompt passed to `claude -p` | Required |
| interval | Run interval (s/m/h/d) | 1h |
| timeout | Timeout (s/m/h/d) | 600s |
| condition | Pre-run shell check (exit 0 = run) | None (always run) |

## License

MIT

---

_under the moonlight, Claude dreams._
