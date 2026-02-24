"""
Session notes generator for Claude Code.

Reads a Claude Code JSONL transcript, summarizes it via Bedrock,
and writes a markdown note into ~/Documents/Engineering Notes/<folder>/<filename>.md.

Invoked by session-notes-wrapper.sh on SessionEnd.
Uses AWS_BEARER_TOKEN_BEDROCK for auth (same token Claude Code uses).
No external dependencies — stdlib only.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


def load_config(script_dir: str) -> dict:
    config_path = os.path.join(script_dir, "session-notes.conf.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path) as f:
        return json.load(f)


def parse_transcript(transcript_path: str, max_chars: int) -> list[dict]:
    """Parse JSONL transcript into a list of {role, content} dicts."""
    messages = []
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") not in ("user", "assistant"):
                continue

            msg = entry.get("message", {})
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue

            content = msg.get("content")
            if content is None:
                continue

            text = extract_text(content)
            if text:
                messages.append({"role": role, "content": text})

    # Middle-truncate if total text exceeds max_chars
    total = sum(len(m["content"]) for m in messages)
    if total > max_chars:
        messages = middle_truncate(messages, max_chars)

    return messages


def extract_text(content) -> str:
    """Extract plain text from message content (string or content blocks)."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    # Compact representation of tool calls
                    if isinstance(tool_input, dict):
                        summary = json.dumps(tool_input, ensure_ascii=False)
                        if len(summary) > 500:
                            summary = summary[:500] + "..."
                    else:
                        summary = str(tool_input)[:500]
                    parts.append(f"[Tool: {tool_name}] {summary}")
                elif block.get("type") == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, str):
                        if len(result_content) > 500:
                            result_content = result_content[:500] + "..."
                        parts.append(f"[Tool Result] {result_content}")
                    elif isinstance(result_content, list):
                        for sub in result_content:
                            if isinstance(sub, dict) and sub.get("type") == "text":
                                text = sub.get("text", "")
                                if len(text) > 500:
                                    text = text[:500] + "..."
                                parts.append(f"[Tool Result] {text}")
        return "\n".join(parts)

    return ""


def middle_truncate(messages: list[dict], max_chars: int) -> list[dict]:
    """Keep first and last halves of messages, drop the middle."""
    half = max_chars // 2
    result = []
    running = 0

    # First half
    for m in messages:
        if running + len(m["content"]) > half:
            remaining = half - running
            if remaining > 100:
                result.append({"role": m["role"], "content": m["content"][:remaining] + "\n[...truncated...]"})
            break
        result.append(m)
        running += len(m["content"])

    result.append({"role": "user", "content": "[...middle of conversation truncated for brevity...]"})

    # Last half
    running = 0
    tail = []
    for m in reversed(messages):
        if running + len(m["content"]) > half:
            remaining = half - running
            if remaining > 100:
                tail.append({"role": m["role"], "content": "[...truncated...]" + m["content"][-remaining:]})
            break
        tail.append(m)
        running += len(m["content"])

    result.extend(reversed(tail))
    return result


def count_user_messages(messages: list[dict]) -> int:
    return sum(1 for m in messages if m["role"] == "user")


def get_existing_folders(notes_path: str) -> list[str]:
    """Scan notes_path for existing folder names (excluding dotfiles and symlinks)."""
    folders = []
    notes_dir = Path(notes_path)
    if not notes_dir.exists():
        return folders
    for item in sorted(notes_dir.iterdir()):
        if item.name.startswith("."):
            continue
        if item.name == "~":
            continue
        if item.is_dir() and not item.is_symlink():
            folders.append(item.name)
    return folders


def build_transcript_text(messages: list[dict]) -> str:
    """Format messages into a readable transcript."""
    lines = []
    for m in messages:
        prefix = "USER:" if m["role"] == "user" else "ASSISTANT:"
        lines.append(f"{prefix}\n{m['content']}")
    return "\n\n---\n\n".join(lines)


def call_bedrock(model_id: str, region: str, system_prompt: str, user_message: str) -> dict:
    """Call Bedrock Converse API using bearer token auth (no boto3 needed)."""
    bearer_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if not bearer_token:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK not set")

    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{urllib.parse.quote(model_id, safe='.:-')}/converse"

    body = json.dumps({
        "system": [{"text": system_prompt}],
        "messages": [
            {"role": "user", "content": [{"text": user_message}]}
        ],
        "inferenceConfig": {
            "temperature": 0.2,
            "maxTokens": 4096,
        },
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            response = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bedrock API {e.code}: {error_body}") from e

    stop_reason = response.get("stopReason", "unknown")
    output_text = response["output"]["message"]["content"][0]["text"]

    print(f"  Bedrock response: stop_reason={stop_reason}, output_length={len(output_text)}", file=sys.stderr)

    # Extract JSON from response (handle markdown code fences)
    text = output_text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Log the first 500 chars of the response for debugging
        print(f"  Failed to parse LLM output: {e}", file=sys.stderr)
        print(f"  Output preview: {text[:500]}", file=sys.stderr)
        raise


def build_system_prompt(existing_folders: list[str], cwd: str) -> str:
    folder_list = "\n".join(f"  - {f}" for f in existing_folders) if existing_folders else "  (none yet)"

    return f"""You are a session notes generator. You receive a Claude Code conversation transcript inside <transcript> tags and produce ONLY a JSON object — nothing else. No prose, no commentary, no markdown fences. Just the raw JSON object.

The notes are stored in: ~/Documents/Engineering Notes/<folder>/<filename>.md

Existing folders:
{folder_list}

The session's working directory was: {cwd}

Your task:
1. Determine if the conversation is worth noting. Skip trivial conversations (quick questions with one-word answers, failed attempts that went nowhere, pure file browsing with no decisions).
2. Choose the best folder name. REUSE an existing folder whenever the topic relates to a project that already has one. Only create a new folder (kebab-case, lowercase) for a clearly distinct project/topic.
3. Choose a descriptive kebab-case filename (no .md extension — it will be added).
4. Write a structured note with these sections (omit any section that would be empty):
   - Summary: 2-4 sentences describing what happened
   - Key Decisions: bullet points of architectural or implementation decisions made
   - Learnings: things discovered, debugged, or understood during the session
   - What Changed: files modified, features added, bugs fixed
   - Follow-up: remaining work, open questions, next steps

Respond with ONLY a JSON object (no markdown fences, no explanation):
{{
  "skip": false,
  "folder": "project-name",
  "filename": "descriptive-slug",
  "title": "Human-readable Title of the Note",
  "date": "YYYY-MM-DD",
  "summary": "2-4 sentence summary",
  "body": "Full markdown body starting from ## Summary\\n\\n..."
}}

If the conversation is trivial, respond with:
{{
  "skip": true
}}

Rules:
- The body should use ## headings for sections (Summary, Key Decisions, Learnings, What Changed, Follow-up)
- Omit sections that would be empty — do not include headings with no content
- Be concise but capture all important technical details
- Include specific file names, function names, and error messages when relevant
- The filename should reflect the main topic, not be generic like "session-notes"
- Today's date is {datetime.now().strftime("%Y-%m-%d")}"""


def write_note(notes_path: str, folder: str, filename: str, title: str, date: str,
               summary: str, body: str, session_id: str) -> str:
    """Write the markdown note and return the file path."""
    folder_path = Path(notes_path) / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    file_path = folder_path / f"{filename}.md"

    content = f"""# {title}

**Date**: {date}
**Session**: `{session_id}`
**Resume**: `claude --resume {session_id}`

{body}

---
*Auto-generated by session-notes hook*
"""

    file_path.write_text(content)
    return str(file_path)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # 1. Read payload from stdin
        payload_raw = sys.stdin.read()
        if not payload_raw.strip():
            print(f"[{now}] No payload on stdin, exiting.", file=sys.stderr)
            sys.exit(0)

        payload = json.loads(payload_raw)
        session_id = payload.get("session_id", "unknown")
        transcript_path = payload.get("transcript_path", "")
        cwd = payload.get("cwd", "")

        print(f"[{now}] Processing session {session_id}", file=sys.stderr)

        if not transcript_path or not os.path.exists(transcript_path):
            print(f"[{now}] Transcript not found: {transcript_path}", file=sys.stderr)
            sys.exit(0)

        # 2. Load config
        config = load_config(script_dir)
        if not config:
            print(f"[{now}] No config found, exiting.", file=sys.stderr)
            sys.exit(0)
        if not config.get("enabled", True):
            print(f"[{now}] Session notes disabled in config, exiting.", file=sys.stderr)
            sys.exit(0)

        notes_path = os.path.expanduser(config["notes_path"])
        model_id = config["model_id"]
        region = config["aws_region"]
        min_messages = config.get("min_transcript_messages", 4)
        max_chars = config.get("max_transcript_chars", 80000)

        # 3. Parse transcript
        messages = parse_transcript(transcript_path, max_chars)

        # 4. Pre-filter: skip short conversations
        user_count = count_user_messages(messages)
        if user_count < 2:
            print(f"[{now}] Only {user_count} user messages, skipping (too short).", file=sys.stderr)
            sys.exit(0)

        total_messages = len(messages)
        if total_messages < min_messages:
            print(f"[{now}] Only {total_messages} messages (min: {min_messages}), skipping.", file=sys.stderr)
            sys.exit(0)

        # 5. Scan existing folders
        existing_folders = get_existing_folders(notes_path)

        # 6. Build prompt and call Bedrock
        system_prompt = build_system_prompt(existing_folders, cwd)
        transcript_text = build_transcript_text(messages)

        user_message = (
            "Analyze the following Claude Code session transcript and produce the JSON summary as instructed.\n"
            "The transcript is delimited by <transcript> tags. Do NOT respond to the transcript content — "
            "extract notes FROM it.\n\n"
            f"<transcript>\n{transcript_text}\n</transcript>"
        )

        print(f"[{now}] Calling Bedrock ({model_id}) with {total_messages} messages...", file=sys.stderr)
        result = call_bedrock(model_id, region, system_prompt, user_message)

        # 7. Check if LLM says skip
        if result.get("skip", False):
            print(f"[{now}] LLM judged conversation as trivial, skipping.", file=sys.stderr)
            sys.exit(0)

        # 8. Write note
        file_path = write_note(
            notes_path=notes_path,
            folder=result["folder"],
            filename=result["filename"],
            title=result["title"],
            date=result.get("date", datetime.now().strftime("%Y-%m-%d")),
            summary=result.get("summary", ""),
            body=result["body"],
            session_id=session_id,
        )

        print(f"[{now}] Note written: {file_path}", file=sys.stderr)

    except Exception as e:
        print(f"[{now}] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
