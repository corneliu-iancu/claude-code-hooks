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
                        if len(summary) > 1500:
                            summary = summary[:1500] + "..."
                    else:
                        summary = str(tool_input)[:1500]
                    parts.append(f"[Tool: {tool_name}] {summary}")
                elif block.get("type") == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, str):
                        if len(result_content) > 1500:
                            result_content = result_content[:1500] + "..."
                        parts.append(f"[Tool Result] {result_content}")
                    elif isinstance(result_content, list):
                        for sub in result_content:
                            if isinstance(sub, dict) and sub.get("type") == "text":
                                text = sub.get("text", "")
                                if len(text) > 1500:
                                    text = text[:1500] + "..."
                                parts.append(f"[Tool Result] {text}")
        return "\n".join(parts)

    return ""


def extract_activity_metadata(transcript_path: str) -> dict:
    """Pre-extract structured metadata from tool calls in the transcript.

    Scans the raw JSONL for tool usage patterns and extracts:
    - files_read, files_written, files_edited: file paths touched
    - commands_run: bash commands executed
    - searches: grep/glob search patterns
    - errors: error messages encountered
    """
    files_read = set()
    files_written = set()
    files_edited = set()
    commands_run = []
    searches = []
    errors = []

    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            content = msg.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue

                if block.get("type") == "tool_use":
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    if not isinstance(tool_input, dict):
                        continue

                    if tool_name == "Read":
                        path = tool_input.get("file_path", "")
                        if path:
                            files_read.add(path)
                    elif tool_name == "Write":
                        path = tool_input.get("file_path", "")
                        if path:
                            files_written.add(path)
                    elif tool_name == "Edit":
                        path = tool_input.get("file_path", "")
                        if path:
                            files_edited.add(path)
                    elif tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        if cmd:
                            commands_run.append(cmd)
                    elif tool_name in ("Grep", "Glob"):
                        pattern = tool_input.get("pattern", "")
                        path = tool_input.get("path", "")
                        if pattern:
                            searches.append(f"{tool_name}: {pattern}" + (f" in {path}" if path else ""))

                elif block.get("type") == "tool_result":
                    is_error = block.get("is_error", False)
                    if is_error:
                        result_content = block.get("content", "")
                        if isinstance(result_content, str) and result_content.strip():
                            errors.append(result_content[:500])
                        elif isinstance(result_content, list):
                            for sub in result_content:
                                if isinstance(sub, dict) and sub.get("type") == "text":
                                    errors.append(sub.get("text", "")[:500])

    return {
        "files_read": sorted(files_read),
        "files_written": sorted(files_written),
        "files_edited": sorted(files_edited),
        "commands_run": commands_run,
        "searches": searches,
        "errors": errors,
    }


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
            "maxTokens": 8192,
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


def build_system_prompt(existing_folders: list[str], cwd: str, activity: dict) -> str:
    folder_list = "\n".join(f"  - {f}" for f in existing_folders) if existing_folders else "  (none yet)"

    # Build activity context block
    activity_lines = []
    if activity.get("files_read"):
        activity_lines.append("Files read:\n" + "\n".join(f"  - {f}" for f in activity["files_read"]))
    if activity.get("files_written"):
        activity_lines.append("Files created:\n" + "\n".join(f"  - {f}" for f in activity["files_written"]))
    if activity.get("files_edited"):
        activity_lines.append("Files edited:\n" + "\n".join(f"  - {f}" for f in activity["files_edited"]))
    if activity.get("commands_run"):
        # Deduplicate and show unique commands (limit to 30)
        unique_cmds = list(dict.fromkeys(activity["commands_run"]))[:30]
        activity_lines.append("Commands run:\n" + "\n".join(f"  - `{c[:200]}`" for c in unique_cmds))
    if activity.get("searches"):
        activity_lines.append("Searches performed:\n" + "\n".join(f"  - {s}" for s in activity["searches"][:20]))
    if activity.get("errors"):
        activity_lines.append("Errors encountered:\n" + "\n".join(f"  - {e[:300]}" for e in activity["errors"][:10]))

    activity_block = "\n\n".join(activity_lines) if activity_lines else "(no tool activity extracted)"

    return f"""You are a senior engineering session notes generator. You receive a Claude Code conversation transcript and a structured activity log, and produce ONLY a JSON object — nothing else. No prose, no commentary, no markdown fences. Just the raw JSON object.

The notes are stored in: ~/Documents/Engineering Notes/<folder>/<filename>.md

Existing folders:
{folder_list}

The session's working directory was: {cwd}

<activity_log>
{activity_block}
</activity_log>

Your task:
1. Determine if the conversation is worth noting. Skip trivial conversations (quick questions with one-word answers, failed attempts that went nowhere, pure file browsing with no decisions).
2. Choose the best folder name. REUSE an existing folder whenever the topic relates to a project that already has one. Only create a new folder (kebab-case, lowercase) for a clearly distinct project/topic.
3. Choose a descriptive kebab-case filename (no .md extension — it will be added).
4. Choose 2-5 descriptive tags for the session (e.g., "refactoring", "debugging", "new-feature", "performance", "devops", "testing", "architecture", "bugfix", "documentation", "api-design").
5. Write a thorough, detailed note with these sections (omit any section that would be empty):

   ## Summary
   3-6 sentences. What was the goal? What approach was taken? What was the outcome? Include enough context that someone reading this 6 months from now can understand the session without re-reading the transcript.

   ## Key Decisions
   Bullet points of architectural, implementation, or design decisions made. For each decision, include:
   - **What** was decided
   - **Why** (the reasoning, tradeoffs considered, alternatives rejected)
   - **Impact** (what this affects going forward)

   ## Problems Encountered
   Bullet points of obstacles, errors, dead ends, and how they were resolved. Include:
   - The problem or error (with specific error messages if available)
   - Root cause (if identified)
   - The fix or workaround applied
   This section is critical for future debugging — be specific.

   ## What Changed
   A precise list of changes made. For each file touched, briefly describe what was modified and why. Group by area if many files changed. Include:
   - Files created, modified, or deleted
   - Features added or removed
   - Configuration changes
   - Dependencies added/removed

   ## Technical Context
   Capture important architectural understanding gained during the session. Things like:
   - How components connect or interact
   - Data flow or control flow insights
   - System constraints or invariants discovered
   - API contracts or interfaces understood
   This section preserves institutional knowledge that would otherwise be lost.

   ## Code Snippets
   Include 1-3 short, important code snippets (max ~15 lines each) that represent key implementations, patterns, or solutions from the session. Use fenced code blocks with language tags. Only include snippets that would be genuinely useful for future reference — the "aha moment" code, not boilerplate.

   ## Learnings
   Things discovered, debugged, or understood during the session. Focus on transferable knowledge:
   - Library/framework behavior that was non-obvious
   - Performance characteristics observed
   - Edge cases or gotchas identified
   - Patterns that worked well (or didn't)

   ## Follow-up
   Remaining work, open questions, next steps. Be specific:
   - What exactly still needs to be done
   - Known issues or tech debt introduced
   - Questions that need answers before proceeding
   - Risks or concerns to watch for

Respond with ONLY a JSON object (no markdown fences, no explanation):
{{
  "skip": false,
  "folder": "project-name",
  "filename": "descriptive-slug",
  "title": "Human-readable Title of the Note",
  "date": "YYYY-MM-DD",
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "3-6 sentence summary",
  "body": "Full markdown body starting from ## Summary\\n\\n..."
}}

If the conversation is trivial, respond with:
{{
  "skip": true
}}

Rules:
- The body MUST use ## headings for sections
- Omit sections that would be genuinely empty — but err on the side of including content
- Be thorough — capture ALL important technical details, specific file paths, function names, error messages, and version numbers
- The filename should reflect the main topic, not be generic like "session-notes"
- Code snippets in the body should use fenced code blocks with language identifiers
- Write for your future self: include enough context to be useful months later
- Prefer concrete specifics over vague generalities (say "added retry logic to fetch_user() in api/client.py" not "updated some API code")
- Today's date is {datetime.now().strftime("%Y-%m-%d")}"""


def write_note(notes_path: str, folder: str, filename: str, title: str, date: str,
               summary: str, body: str, session_id: str, tags: list[str] | None = None,
               activity: dict | None = None) -> str:
    """Write the markdown note and return the file path."""
    folder_path = Path(notes_path) / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    file_path = folder_path / f"{filename}.md"

    # Build YAML frontmatter
    tags_yaml = "\n".join(f"  - {t}" for t in (tags or []))
    frontmatter = f"""---
title: "{title}"
date: {date}
session: {session_id}
tags:
{tags_yaml}
---"""

    # Build activity summary section
    activity_section = ""
    if activity:
        activity_parts = []
        all_files = set()
        for key in ("files_read", "files_written", "files_edited"):
            all_files.update(activity.get(key, []))
        if all_files:
            # Shorten paths: strip common prefix
            sorted_files = sorted(all_files)
            activity_parts.append("**Files touched**: " + ", ".join(f"`{os.path.basename(f)}`" for f in sorted_files))
        if activity.get("commands_run"):
            unique_cmds = list(dict.fromkeys(activity["commands_run"]))
            # Only show interesting commands (skip simple ls, cd, etc.)
            interesting = [c for c in unique_cmds if len(c) > 5][:10]
            if interesting:
                activity_parts.append("**Key commands**: " + ", ".join(f"`{c[:80]}`" for c in interesting))
        if activity.get("errors"):
            activity_parts.append(f"**Errors hit**: {len(activity['errors'])}")
        if activity_parts:
            activity_section = "\n> " + " | ".join(activity_parts) + "\n"

    content = f"""{frontmatter}

# {title}

**Date**: {date}
**Session**: `{session_id}`
**Resume**: `claude --resume {session_id}`
{activity_section}
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

        # 5. Extract structured activity metadata from tool calls
        activity = extract_activity_metadata(transcript_path)
        print(f"[{now}] Activity: {len(activity['files_read'])} reads, "
              f"{len(activity['files_written'])} writes, {len(activity['files_edited'])} edits, "
              f"{len(activity['commands_run'])} commands, {len(activity['errors'])} errors",
              file=sys.stderr)

        # 6. Scan existing folders
        existing_folders = get_existing_folders(notes_path)

        # 7. Build prompt and call Bedrock
        system_prompt = build_system_prompt(existing_folders, cwd, activity)
        transcript_text = build_transcript_text(messages)

        user_message = (
            "Analyze the following Claude Code session transcript and produce the JSON summary as instructed.\n"
            "The transcript is delimited by <transcript> tags. Do NOT respond to the transcript content — "
            "extract notes FROM it.\n\n"
            f"<transcript>\n{transcript_text}\n</transcript>"
        )

        print(f"[{now}] Calling Bedrock ({model_id}) with {total_messages} messages...", file=sys.stderr)
        result = call_bedrock(model_id, region, system_prompt, user_message)

        # 8. Check if LLM says skip
        if result.get("skip", False):
            print(f"[{now}] LLM judged conversation as trivial, skipping.", file=sys.stderr)
            sys.exit(0)

        # 9. Write note
        file_path = write_note(
            notes_path=notes_path,
            folder=result["folder"],
            filename=result["filename"],
            title=result["title"],
            date=result.get("date", datetime.now().strftime("%Y-%m-%d")),
            summary=result.get("summary", ""),
            body=result["body"],
            session_id=session_id,
            tags=result.get("tags"),
            activity=activity,
        )

        print(f"[{now}] Note written: {file_path}", file=sys.stderr)

    except Exception as e:
        print(f"[{now}] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
