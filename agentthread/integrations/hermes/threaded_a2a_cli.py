"""CLI entrypoint for AgentThread-wrapped Hermes A2A consultation.

This command is intentionally scoped to consultation/review/brainstorming. Project
work that should wake another agent must still use Multica issue creation.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from agentthread.store import Store

from .a2a_thread_wrapper import make_a2a_send_func, send_threaded_a2a


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-thread-a2a",
        description="Send a Hermes A2A consultation while recording AgentThread state.",
    )
    parser.add_argument("--db", help="SQLite DB path. Defaults to ~/.agent-thread/agentthread.db")
    parser.add_argument("--owner", required=True, help="Responsible owner agent, e.g. prd-bot/product-dev/media")
    parser.add_argument("--to", required=True, help="Target A2A gateway key, e.g. prd/dev/media")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--sender", help="Display sender for a2a-chat transport; defaults to owner")
    parser.add_argument("--sid", help="A2A transcript/session id; defaults to new thread_id")
    parser.add_argument("--thread-id", help="Reuse an existing AgentThread thread")
    parser.add_argument(
        "--thread-type",
        default="consultation",
        choices=["consultation"],
        help="Only consultation is supported here. Use Multica issue create for task handoff.",
    )
    parser.add_argument("--source-platform")
    parser.add_argument("--source-chat")
    parser.add_argument("--artifact", action="append", default=[], help="JSON object. Can be repeated.")
    parser.add_argument("--next-action-json", help="JSON object for next_action")
    parser.add_argument("--metadata-json", help="JSON object for thread metadata")
    parser.add_argument(
        "--mock-reply",
        help="Testing/dry-run mode: do not call Hermes gateway; use this reply text as transport result.",
    )
    parser.add_argument(
        "--a2a-script-path",
        help="Directory containing Hermes a2a_send.py. Defaults to the shared ~/.hermes skill path.",
    )
    args = parser.parse_args(argv)

    store = Store(args.db)
    source = _source(args.source_platform, args.source_chat)
    artifacts = [_json_object(value, parser, "--artifact") for value in args.artifact]
    next_action = _json_object(args.next_action_json, parser, "--next-action-json") if args.next_action_json else None
    metadata = _json_object(args.metadata_json, parser, "--metadata-json") if args.metadata_json else None

    if args.mock_reply is not None:
        def send_func(**_: Any) -> str:
            return args.mock_reply
    else:
        send_func = make_a2a_send_func(script_path=args.a2a_script_path)

    result = send_threaded_a2a(
        store,
        owner=args.owner,
        to=args.to,
        topic=args.topic,
        message=args.message,
        send_func=send_func,
        thread_id=args.thread_id,
        thread_type=args.thread_type,
        source=source,
        artifacts=artifacts,
        sender=args.sender,
        sid=args.sid,
        next_action=next_action,
        metadata=metadata,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _source(platform: str | None, chat_id: str | None) -> dict[str, Any] | None:
    source: dict[str, Any] = {}
    if platform is not None:
        source["platform"] = platform
    if chat_id is not None:
        source["chat_id"] = str(chat_id)
    return source or None


def _json_object(value: str, parser: argparse.ArgumentParser, flag: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid JSON for {flag}: {exc.msg}")
    if not isinstance(parsed, dict):
        parser.error(f"{flag} must be a JSON object")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
