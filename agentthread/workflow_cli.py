"""High-level AgentThread workflow CLI.

This is the stable entrypoint for users and agents:
- ask: consultation with durable AgentThread state
- task create: task handoff with a durable task thread and backend reference
- notify: human notification record with agent-target guardrail
- audit: lightweight compliance checks
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .integrations.hermes.a2a_thread_wrapper import make_a2a_send_func, send_threaded_a2a
from .store import Store

AGENT_TARGETS = {
    "prd",
    "dev",
    "media",
    "prd-bot",
    "product-dev",
    "产品侠",
    "产品虾",
    "研发侠",
    "媒体侠",
    "@prd_niuma_bot",
    "@claw_niumabot",
    "@Claw_NiumaBot",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentthread")
    parser.add_argument("--db", help="SQLite DB path. Defaults to ~/.agent-thread/agentthread.db")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="Ask another agent for consultation; always records AgentThread state.")
    ask.add_argument("--owner", required=True)
    ask.add_argument("--to", required=True)
    ask.add_argument("--sender")
    ask.add_argument("--topic", required=True)
    ask.add_argument("--message", required=True)
    ask.add_argument("--artifact", action="append", default=[])
    ask.add_argument("--mock-reply")
    ask.add_argument("--a2a-script-path")

    task = sub.add_parser("task", help="Task workflows")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_create = task_sub.add_parser("create", help="Create a task handoff thread and task backend reference.")
    task_create.add_argument("--owner", required=True)
    task_create.add_argument("--assignee", required=True)
    task_create.add_argument("--topic", required=True)
    task_create.add_argument("--description", required=True)
    task_create.add_argument("--backend", choices=["mock", "multica", "github", "linear"], help="Task backend; required so tasks cannot silently go over chat.")
    task_create.add_argument("--artifact", action="append", default=[])

    notify = sub.add_parser("notify", help="Record a human notification; rejects agent targets.")
    notify.add_argument("--owner", required=True)
    notify.add_argument("--target", required=True)
    notify.add_argument("--message", required=True)

    status = sub.add_parser("status", help="List recent threads for an owner.")
    status.add_argument("--owner", required=True)
    status.add_argument("--limit", type=int, default=20)

    audit = sub.add_parser("audit", help="Run lightweight workflow compliance audit.")
    audit.add_argument("--a2a-transcript-dir", default=str(Path("~/.hermes/a2a-transcripts").expanduser()))

    args = parser.parse_args(argv)
    store = Store(args.db)

    if args.command == "ask":
        result = _ask(args, store, parser)
    elif args.command == "task" and args.task_command == "create":
        result = _task_create(args, store, parser)
    elif args.command == "notify":
        result = _notify(args, store, parser)
    elif args.command == "status":
        result = store.recent_threads(owner=args.owner, limit=args.limit)
    elif args.command == "audit":
        result = _audit(args, store)
    else:
        parser.error("Unsupported command")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _ask(args: argparse.Namespace, store: Store, parser: argparse.ArgumentParser) -> dict[str, Any]:
    artifacts = [_json_object(value, parser, "--artifact") for value in args.artifact]
    if args.mock_reply is not None:
        def send_func(**_: Any) -> str:
            return args.mock_reply
    else:
        send_func = make_a2a_send_func(script_path=args.a2a_script_path)
    return send_threaded_a2a(
        store,
        owner=args.owner,
        to=args.to,
        topic=args.topic,
        message=args.message,
        send_func=send_func,
        sender=args.sender,
        artifacts=artifacts,
    )


def _task_create(args: argparse.Namespace, store: Store, parser: argparse.ArgumentParser) -> dict[str, Any]:
    if not args.backend:
        parser.error("--backend is required for task create; tasks must use a task backend, not chat/A2A")
    artifacts = [_json_object(value, parser, "--artifact") for value in args.artifact]
    task_ref = {"backend": args.backend, "id": f"mock:{args.topic}" if args.backend == "mock" else None}
    thread = store.create_thread(
        type="task",
        owner=args.owner,
        participants=[args.assignee],
        topic=args.topic,
        status="waiting_on_participant",
        latest_summary=f"Task assigned to {args.assignee}: {args.topic}",
        next_action={"actor": args.assignee, "description": args.description},
        artifacts=[*artifacts, {"type": "task_ref", **task_ref}],
        created_by={"type": "agent", "id": args.owner},
        metadata={"backend": args.backend},
    )
    event = store.append_event(
        thread["thread_id"],
        type="task_created",
        actor=args.owner,
        target=args.assignee,
        summary=f"Created task for {args.assignee} via {args.backend}.",
        content=args.description,
        transport={"kind": "task_backend", "backend": args.backend},
    )
    inbox = store.create_inbox_item(
        agent=args.assignee,
        thread_id=thread["thread_id"],
        kind="assignment",
        summary=args.topic,
        metadata={"backend": args.backend},
    )
    return {"thread": thread, "event": event, "inbox_item": inbox, "task_ref": task_ref}


def _notify(args: argparse.Namespace, store: Store, parser: argparse.ArgumentParser) -> dict[str, Any]:
    if _is_agent_target(args.target):
        parser.error("notify target looks like an agent target; use ask for consultation or task create for work delegation")
    thread = store.create_thread(
        type="notification",
        owner=args.owner,
        topic=f"Notify {args.target}",
        status="done",
        latest_summary=args.message,
        created_by={"type": "agent", "id": args.owner},
    )
    event = store.append_event(
        thread["thread_id"],
        type="human_notified",
        actor=args.owner,
        target=args.target,
        summary=f"Notified {args.target}.",
        content=args.message,
        transport={"kind": "human_notification"},
    )
    return {"thread": thread, "event": event}


def _audit(args: argparse.Namespace, store: Store) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    known_sids = _known_a2a_sids(store)
    transcript_dir = Path(args.a2a_transcript_dir).expanduser()
    if transcript_dir.exists():
        for path in sorted(transcript_dir.glob("*.jsonl")):
            sid = path.stem
            if sid not in known_sids:
                findings.append(
                    {
                        "level": "warn",
                        "code": "raw_a2a_without_thread",
                        "sid": sid,
                        "path": str(path),
                        "message": "A2A transcript has no matching AgentThread transport sid.",
                    }
                )
    return {"status": "ok" if not findings else "warn", "findings": findings}


def _known_a2a_sids(store: Store) -> set[str]:
    sids: set[str] = set()
    try:
        with store._connect() as conn:  # internal read for audit; no public event search API yet
            rows = conn.execute("SELECT transport_json FROM events WHERE transport_json IS NOT NULL").fetchall()
    except sqlite3.Error:
        return sids
    for row in rows:
        try:
            transport = json.loads(row["transport_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if transport.get("kind") == "hermes_a2a" and transport.get("sid"):
            sids.add(str(transport["sid"]))
    return sids


def _is_agent_target(target: str) -> bool:
    normalized = target.strip()
    return normalized in AGENT_TARGETS or normalized.lower() in {item.lower() for item in AGENT_TARGETS}


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
