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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import allowed_task_backends, load_config, write_default_config
from .integrations.hermes.a2a_thread_wrapper import make_a2a_send_func, send_threaded_a2a
from .policy import default_policy, ensure_backend_allowed
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
    parser.add_argument("--config", help="Path to agentthread.yaml")
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
    task_create.add_argument("--allowed-task-backend", action="append", default=[], help="Policy allow-list for task backends. Can be repeated.")
    task_create.add_argument("--config", dest="command_config", help="Path to agentthread.yaml")
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
    audit.add_argument("--stale-hours", type=float, default=24.0)

    doctor = sub.add_parser("doctor", help="Check local AgentThread workflow readiness.")
    doctor.add_argument("--config", dest="command_config", help="Path to agentthread.yaml")
    sub.add_parser("policy", help="Print active workflow policy rules.")

    init = sub.add_parser("init", help="Create a starter agentthread.yaml")
    init.add_argument("--dir", default=".")
    init.add_argument("--overwrite", action="store_true")

    args = parser.parse_args(argv)
    store = Store(args.db)
    config_path = getattr(args, "command_config", None) or args.config
    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        parser.error(f"Config not found: {exc}")

    if args.command == "ask":
        result = _ask(args, store, parser)
    elif args.command == "task" and args.task_command == "create":
        result = _task_create(args, store, parser, config)
    elif args.command == "notify":
        result = _notify(args, store, parser)
    elif args.command == "status":
        result = store.recent_threads(owner=args.owner, limit=args.limit)
    elif args.command == "audit":
        result = _audit(args, store)
    elif args.command == "doctor":
        result = _doctor(store, config=config, config_path=config_path)
    elif args.command == "policy":
        result = default_policy()
    elif args.command == "init":
        path = write_default_config(args.dir, overwrite=args.overwrite)
        result = {"status": "ok", "config_path": str(path)}
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


def _task_create(args: argparse.Namespace, store: Store, parser: argparse.ArgumentParser, config: dict[str, Any]) -> dict[str, Any]:
    if not args.backend:
        parser.error("--backend is required for task create; tasks must use a task backend, not chat/A2A")
    allowed = args.allowed_task_backend or allowed_task_backends(config)
    try:
        ensure_backend_allowed(args.backend, allowed)
    except ValueError as exc:
        parser.error(str(exc))
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
    findings.extend(_stale_thread_findings(store, stale_hours=args.stale_hours))
    return {"status": "ok" if not findings else "warn", "findings": findings}


def _doctor(store: Store, *, config: dict[str, Any] | None = None, config_path: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    config = config or {}
    try:
        with store._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        checks.append({"code": "database_writable", "status": "ok", "message": str(store.db_path)})
    except sqlite3.Error as exc:
        checks.append({"code": "database_writable", "status": "fail", "message": str(exc)})
    policy = default_policy()
    checks.append({"code": "policy_loaded", "status": "ok", "message": f"{len(policy['rules'])} rules"})
    checks.append({"code": "raw_transport_disabled", "status": "ok", "message": "Use ask/task/notify high-level workflows."})
    if config_path:
        checks.append({"code": "config_loaded", "status": "ok", "message": config_path})
        agents = config.get("agents") or {}
        backends = config.get("task_backends") or {}
        checks.append({"code": "agents_configured", "status": "ok" if agents else "warn", "message": str(len(agents))})
        checks.append({"code": "task_backends_configured", "status": "ok" if backends else "warn", "message": str(len(backends))})
    status = "fail" if any(check["status"] == "fail" for check in checks) else "ok"
    return {"status": status, "checks": checks}


def _stale_thread_findings(store: Store, *, stale_hours: float) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    threshold_seconds = stale_hours * 3600
    now = datetime.now(timezone.utc)
    with store._connect() as conn:
        rows = conn.execute(
            "SELECT thread_id, status, owner, topic, updated_at FROM threads WHERE status IN ('open','waiting_on_owner','waiting_on_participant','in_progress','blocked')"
        ).fetchall()
    for row in rows:
        updated = _parse_utc(row["updated_at"])
        age = (now - updated).total_seconds()
        if age >= threshold_seconds:
            findings.append(
                {
                    "level": "warn",
                    "code": "stale_active_thread",
                    "thread_id": row["thread_id"],
                    "owner": row["owner"],
                    "status": row["status"],
                    "topic": row["topic"],
                    "age_hours": round(age / 3600, 2),
                    "message": "Active thread has not been updated within the configured threshold.",
                }
            )
    return findings


def _parse_utc(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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
