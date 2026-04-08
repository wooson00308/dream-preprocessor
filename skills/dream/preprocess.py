"""Transcript JSONL preprocessor for /dream.

Extracts user text + assistant text from raw transcript JSONL files,
outputs lightweight markdown files ready for LLM consumption.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def get_project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def get_dream_meta(slug: str) -> dict:
    """Read dream_meta.md and return processed transcript list."""
    meta_path = get_project_dir(slug) / "memory" / "dream_meta.md"
    if not meta_path.exists():
        return {"last_dream": None, "processed": set()}

    content = meta_path.read_text(encoding="utf-8")
    processed = set()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- ") and line.endswith(".jsonl"):
            processed.add(line[2:])

    return {"processed": processed}


def find_unprocessed_transcripts(slug: str) -> list[Path]:
    """Find transcript JSONL files not yet processed by /dream."""
    project_dir = get_project_dir(slug)
    meta = get_dream_meta(slug)
    processed = meta["processed"]

    transcripts = []
    for f in sorted(project_dir.glob("*.jsonl")):
        if f.name not in processed:
            transcripts.append(f)

    return transcripts


def _compress_code_blocks(text: str) -> str:
    """Compress code blocks: keep 3 lines or less, truncate longer ones."""
    result = []
    in_code = False
    code_lines = []
    code_fence = ""

    for line in text.split("\n"):
        if not in_code and re.match(r"^```", line):
            in_code = True
            code_fence = line
            code_lines = []
        elif in_code and re.match(r"^```\s*$", line):
            in_code = False
            if len(code_lines) <= 3:
                result.append(code_fence)
                result.extend(code_lines)
                result.append("```")
            else:
                result.append(code_fence)
                result.append(code_lines[0])
                result.append(f"... ({len(code_lines)}줄 생략)")
                result.append("```")
        elif in_code:
            code_lines.append(line)
        else:
            result.append(line)

    # Handle unclosed code block
    if in_code and code_lines:
        if len(code_lines) <= 3:
            result.append(code_fence)
            result.extend(code_lines)
        else:
            result.append(code_fence)
            result.append(code_lines[0])
            result.append(f"... ({len(code_lines)}줄 생략)")

    return "\n".join(result)


def extract_conversation(transcript_path: Path) -> list[dict]:
    """Extract meaningful conversation turns from a transcript JSONL."""
    lines = transcript_path.read_text(encoding="utf-8").strip().split("\n")
    conversation = []

    for line in lines:
        try:
            obj = json.loads(line)
            msg_type = obj.get("type", "")
            timestamp = obj.get("timestamp", "")

            if msg_type == "user":
                content = obj.get("message", {}).get("content", "")
                if isinstance(content, str):
                    text = content.strip()
                    # Skip system/command messages and short noise
                    if text and not text.startswith("<") and len(text) > 2:
                        conversation.append({
                            "role": "user",
                            "text": text,
                            "time": timestamp,
                        })

            elif msg_type == "assistant":
                content = obj.get("message", {}).get("content", [])
                if isinstance(content, list):
                    texts = []
                    tool_names = []
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            t = block.get("text", "").strip()
                            if t:
                                texts.append(t)
                        elif block.get("type") == "tool_use":
                            tool_names.append(block.get("name", "?"))

                    if texts:
                        conversation.append({
                            "role": "assistant",
                            "text": "\n".join(texts),
                            "time": timestamp,
                        })
                    elif tool_names:
                        conversation.append({
                            "role": "assistant",
                            "text": f"[도구 호출: {', '.join(tool_names)}]",
                            "time": timestamp,
                        })

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return conversation


def _merge_consecutive_tool_calls(turns: list[dict]) -> list[dict]:
    """Merge consecutive assistant tool-call-only turns into one line."""
    merged = []
    tool_buffer = []

    for turn in turns:
        is_tool = turn["role"] == "assistant" and turn["text"].startswith("[도구 호출:")

        if is_tool:
            # Extract tool names from "[도구 호출: X, Y]"
            names_str = turn["text"][len("[도구 호출: "):-1]
            tool_buffer.extend(n.strip() for n in names_str.split(","))
        else:
            if tool_buffer:
                # Collapse buffer: count duplicates
                merged.append({
                    "role": "assistant",
                    "text": f"[도구: {_summarize_tools(tool_buffer)}]",
                    "time": turn["time"],
                })
                tool_buffer = []
            merged.append(turn)

    # Flush remaining
    if tool_buffer:
        merged.append({
            "role": "assistant",
            "text": f"[도구: {_summarize_tools(tool_buffer)}]",
            "time": "",
        })

    return merged


def _summarize_tools(names: list[str]) -> str:
    """Summarize tool names with counts: ['Bash', 'Read', 'Read'] -> 'Bash, Read x2'"""
    counts: dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1

    parts = []
    for name, count in counts.items():
        if count > 1:
            parts.append(f"{name} x{count}")
        else:
            parts.append(name)
    return ", ".join(parts)


def conversation_to_markdown(session_id: str, conversation: list[dict]) -> str:
    """Convert conversation list to a compact markdown format."""
    if not conversation:
        return ""

    # Merge consecutive tool calls
    conversation = _merge_consecutive_tool_calls(conversation)

    lines = [f"## 세션 {session_id[:8]}"]

    # Get date from first timestamp
    first_time = conversation[0].get("time", "")
    if first_time:
        try:
            dt = datetime.fromisoformat(first_time.replace("Z", "+00:00"))
            lines[0] += f" ({dt.strftime('%Y-%m-%d %H:%M')})"
        except (ValueError, TypeError):
            pass

    lines.append("")

    for turn in conversation:
        role = "U" if turn["role"] == "user" else "A"
        text = turn["text"]

        # Compress code blocks
        text = _compress_code_blocks(text)

        lines.append(f"{role}: {text}")
        lines.append("")

    return "\n".join(lines)


def preprocess_project(slug: str, output_dir: Path | None = None, limit: int = 5) -> None:
    """Preprocess unprocessed transcripts for a project."""
    unprocessed = find_unprocessed_transcripts(slug)

    if not unprocessed:
        print(f"[{slug}] 미처리 transcript 없음")
        return

    print(f"[{slug}] 미처리 transcript {len(unprocessed)}개 발견, {min(limit, len(unprocessed))}개 처리")

    # Output directory
    if output_dir is None:
        output_dir = get_project_dir(slug) / "memory" / "_dream_prep"
    output_dir.mkdir(parents=True, exist_ok=True)

    batch = unprocessed[:limit]
    all_sections = []

    for transcript_path in batch:
        session_id = transcript_path.stem
        conversation = extract_conversation(transcript_path)

        if not conversation:
            continue

        md = conversation_to_markdown(session_id, conversation)
        if md:
            all_sections.append(md)

    if all_sections:
        output_file = output_dir / f"prep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        content = f"# Dream Prep — {slug}\n\n처리 대상: {len(batch)}개 transcript\n\n---\n\n"
        content += "\n---\n\n".join(all_sections)
        output_file.write_text(content, encoding="utf-8")
        print(f"[{slug}] → {output_file} ({len(all_sections)}개 세션)")
    else:
        print(f"[{slug}] 의미 있는 대화 없음")


def list_projects() -> list[str]:
    """List all project slugs that have transcripts."""
    if not PROJECTS_DIR.exists():
        return []
    result = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir() and list(d.glob("*.jsonl")):
            result.append(d.name)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dream-prep",
        description="Preprocess transcript JSONL files for /dream"
    )
    sub = parser.add_subparsers(dest="command")

    # prep
    p_prep = sub.add_parser("prep", help="Preprocess transcripts for a project")
    p_prep.add_argument("--slug", "-s", required=True, help="Project slug (e.g. -Users-yourname)")
    p_prep.add_argument("--limit", "-n", type=int, default=5, help="Max transcripts to process")

    # list
    sub.add_parser("list", help="List projects with transcripts")

    # status
    p_status = sub.add_parser("status", help="Show processing status for a project")
    p_status.add_argument("--slug", "-s", required=True, help="Project slug")

    args = parser.parse_args()

    if args.command == "prep":
        preprocess_project(args.slug, limit=args.limit)
    elif args.command == "list":
        for slug in list_projects():
            count = len(list(get_project_dir(slug).glob("*.jsonl")))
            print(f"  {slug} ({count} transcripts)")
    elif args.command == "status":
        unprocessed = find_unprocessed_transcripts(args.slug)
        total = len(list(get_project_dir(args.slug).glob("*.jsonl")))
        print(f"  전체: {total}, 처리됨: {total - len(unprocessed)}, 미처리: {len(unprocessed)}")
    else:
        parser.print_help()
