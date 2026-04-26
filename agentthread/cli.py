"""JSON CLI for AgentThread MVP0."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .recall import answer_context
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-thread")
    parser.add_argument("--db", help="SQLite DB path. Defaults to ~/.agent-thread/agentthread.db")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--type", required=True)
    create.add_argument("--owner", required=True)
    create.add_argument("--participant", action="append", default=[])
    create.add_argument("--created-by")
    create.add_argument("--source-platform")
    create.add_argument("--source-chat")
    create.add_argument("--topic", required=True)
    create.add_argument("--summary")
    create.add_argument("--status", default="open")
    create.add_argument("--tag", action="append", default=[])
    create.add_argument("--json", dest="json_payload", help="JSON object with structured thread fields")

    update = sub.add_parser("update")
    update.add_argument("thread_id")
    update.add_argument("--status")
    update.add_argument("--topic")
    update.add_argument("--summary")
    update.add_argument("--next-actor")
    update.add_argument("--next-action")
    update.add_argument("--json", dest="json_payload", help="JSON object with structured thread fields")

    get = sub.add_parser("get")
    get.add_argument("thread_id")

    events = sub.add_parser("events")
    events.add_argument("thread_id")
    events.add_argument("--limit", type=int)

    event = sub.add_parser("event")
    event_sub = event.add_subparsers(dest="event_command", required=True)
    event_append = event_sub.add_parser("append")
    event_append.add_argument("thread_id")
    event_append.add_argument("--type", required=True)
    event_append.add_argument("--actor")
    event_append.add_argument("--target")
    event_append.add_argument("--summary")
    event_append.add_argument("--content")

    recent = sub.add_parser("recent")
    recent.add_argument("--owner", required=True)
    recent.add_argument("--source-platform")
    recent.add_argument("--source-chat")
    recent.add_argument("--status")
    recent.add_argument("--limit", type=int, default=20)

    inbox = sub.add_parser("inbox")
    inbox_sub = inbox.add_subparsers(dest="inbox_command", required=True)
    inbox_list = inbox_sub.add_parser("list")
    inbox_list.add_argument("--agent", required=True)
    inbox_list.add_argument("--unread", action="store_true")
    inbox_list.add_argument("--limit", type=int, default=20)
    inbox_read = inbox_sub.add_parser("read")
    inbox_read.add_argument("inbox_id")

    export = sub.add_parser("export")
    export.add_argument("thread_id")

    context = sub.add_parser("answer-context")
    context.add_argument("--owner", required=True)
    context.add_argument("--query", required=True)
    context.add_argument("--source-platform")
    context.add_argument("--source-chat")
    context.add_argument("--participant-hint")
    context.add_argument("--topic-hint")
    context.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    store = Store(args.db)

    if args.command == "create":
        payload = _json_object(args.json_payload, parser)
        result = store.create_thread(
            type=args.type,
            owner=args.owner,
            participants=args.participant,
            topic=args.topic,
            status=args.status,
            created_by=payload.get("created_by", _created_by(args.created_by)),
            source=payload.get("source", _source(args.source_platform, args.source_chat)),
            latest_summary=args.summary,
            next_action=payload.get("next_action"),
            artifacts=payload.get("artifacts"),
            tags=payload.get("tags", args.tag),
            metadata=payload.get("metadata"),
        )
    elif args.command == "update":
        updates: dict[str, Any] = _json_object(args.json_payload, parser)
        if args.status is not None:
            updates["status"] = args.status
        if args.topic is not None:
            updates["topic"] = args.topic
        if args.summary is not None:
            updates["latest_summary"] = args.summary
        if args.next_actor or args.next_action:
            updates["next_action"] = {"actor": args.next_actor, "description": args.next_action}
        result = store.update_thread(args.thread_id, **updates)
        if result is None:
            parser.error(f"Unknown thread_id: {args.thread_id}")
    elif args.command == "get":
        result = store.get_thread(args.thread_id)
        if result is None:
            parser.error(f"Unknown thread_id: {args.thread_id}")
    elif args.command == "events":
        if store.get_thread(args.thread_id) is None:
            parser.error(f"Unknown thread_id: {args.thread_id}")
        result = store.list_events(args.thread_id, limit=args.limit)
    elif args.command == "event" and args.event_command == "append":
        result = store.append_event(
            args.thread_id,
            type=args.type,
            actor=args.actor,
            target=args.target,
            summary=args.summary,
            content=args.content,
        )
    elif args.command == "recent":
        statuses = args.status.split(",") if args.status else None
        result = store.recent_threads(
            owner=args.owner,
            source=_source(args.source_platform, args.source_chat),
            statuses=statuses,
            limit=args.limit,
        )
    elif args.command == "answer-context":
        result = answer_context(
            store,
            owner=args.owner,
            query=args.query,
            source=_source(args.source_platform, args.source_chat),
            participant_hint=args.participant_hint,
            topic_hint=args.topic_hint,
            limit=args.limit,
        )
    elif args.command == "inbox" and args.inbox_command == "list":
        result = store.list_inbox(args.agent, unread_only=args.unread, limit=args.limit)
    elif args.command == "inbox" and args.inbox_command == "read":
        result = store.mark_inbox_read(args.inbox_id)
        if result is None:
            parser.error(f"Unknown inbox_id: {args.inbox_id}")
    elif args.command == "export":
        try:
            result = store.export_thread(args.thread_id)
        except KeyError:
            parser.error(f"Unknown thread_id: {args.thread_id}")
    else:
        parser.error("Unsupported command")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _source(platform: str | None, chat_id: str | None) -> dict[str, Any] | None:
    source: dict[str, Any] = {}
    if platform is not None:
        source["platform"] = platform
    if chat_id is not None:
        source["chat_id"] = str(chat_id)
    return source or None


def _created_by(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {"type": "human", "id": value}


def _json_object(value: str | None, parser: argparse.ArgumentParser) -> dict[str, Any]:
    if value is None:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid JSON: {exc.msg}")
    if not isinstance(parsed, dict):
        parser.error("--json must be a JSON object")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
