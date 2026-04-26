"""AgentThread wrapper for Hermes A2A sends.

The wrapper is intentionally transport-light: callers inject ``send_func`` for
tests or production. The callable is invoked as:

    send_func(to=to, sid=effective_sid, sender=effective_sender, msg=message)

``make_a2a_send_func`` adapts the local Hermes ``a2a_send.py`` helper to that
shape without importing Hermes-specific modules at AgentThread import time.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable


SendFunc = Callable[..., Any]

DEFAULT_A2A_SCRIPT_PATH = Path("~/.hermes/skills/productivity/a2a-chat/scripts").expanduser()


def send_threaded_a2a(
    store: Any,
    *,
    owner: str,
    to: str,
    topic: str,
    message: str,
    send_func: SendFunc,
    thread_id: str | None = None,
    thread_type: str = "consultation",
    source: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    sender: str | None = None,
    sid: str | None = None,
    status_before: str = "waiting_on_participant",
    status_after: str = "answered",
    next_action: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    create_inbox: bool = True,
) -> dict[str, Any]:
    """Send a Hermes A2A message while recording AgentThread collaboration state.

    ``owner`` is the agent responsible for answering future user follow-ups.
    ``to`` is the Hermes A2A participant/gateway key. ``sender`` controls the
    transport display identity; when omitted, the owner is used.
    """

    created_thread = False
    if thread_id is None:
        thread = store.create_thread(
            type=thread_type,
            owner=owner,
            participants=[to],
            topic=topic,
            status=status_before,
            created_by={"type": "agent", "id": owner},
            source=source,
            artifacts=artifacts or [],
            metadata=metadata or {},
        )
        created_thread = True
    else:
        thread = store.get_thread(thread_id)
        if thread is None:
            raise KeyError(f"Unknown thread_id: {thread_id}")

    effective_sender = sender or owner
    effective_sid = sid or thread["thread_id"]

    inbox_item = None
    if created_thread and create_inbox:
        inbox_item = store.create_inbox_item(
            agent=to,
            thread_id=thread["thread_id"],
            kind="assignment",
            summary=f"Hermes A2A request: {topic}",
            metadata={"kind": "hermes_a2a", "sid": effective_sid, "owner": owner},
        )

    outbound_event = store.append_event(
        thread["thread_id"],
        type="message_sent",
        actor=effective_sender,
        target=to,
        summary=f"Sent Hermes A2A message to {to}.",
        content=message,
        transport={"kind": "hermes_a2a", "sid": effective_sid, "to": to},
    )

    raw_reply = send_func(to=to, sid=effective_sid, sender=effective_sender, msg=message)
    reply = _reply_text(raw_reply)

    inbound_event = store.append_event(
        thread["thread_id"],
        type="message_received",
        actor=to,
        target=owner,
        summary=f"Received Hermes A2A reply from {to}.",
        content=reply,
        transport={"kind": "hermes_a2a", "sid": effective_sid, "to": to},
    )

    updates: dict[str, Any] = {
        "status": status_after,
        "latest_summary": _summary(to, reply),
    }
    if next_action is not None:
        updates["next_action"] = next_action
    thread = store.update_thread(thread["thread_id"], **updates)

    result = {
        "thread": thread,
        "outbound_event": outbound_event,
        "inbound_event": inbound_event,
        "reply": reply,
    }
    if inbox_item is not None:
        result["inbox_item"] = inbox_item
    return result


def make_a2a_send_func(script_path: str | Path | None = None) -> SendFunc:
    """Return a callable backed by Hermes ``send_a2a_message``.

    The import happens only when this helper is called. ``script_path`` defaults
    to ``~/.hermes/skills/productivity/a2a-chat/scripts`` and is temporarily
    added to ``sys.path`` for the import.
    """

    module_dir = Path(script_path).expanduser() if script_path is not None else DEFAULT_A2A_SCRIPT_PATH
    module_dir_str = str(module_dir)
    inserted = False
    if module_dir_str not in sys.path:
        sys.path.insert(0, module_dir_str)
        inserted = True
    try:
        module = importlib.import_module("a2a_send")
    finally:
        if inserted:
            try:
                sys.path.remove(module_dir_str)
            except ValueError:
                pass

    send_a2a_message = module.send_a2a_message

    def send_func(*, to: str, sid: str, sender: str, msg: str) -> Any:
        return send_a2a_message(to=to, sid=sid, sender=sender, msg=msg)

    return send_func


def _reply_text(reply: Any) -> str:
    if isinstance(reply, str):
        return reply
    if isinstance(reply, dict):
        for key in ("reply", "content", "message", "text"):
            value = reply.get(key)
            if isinstance(value, str):
                return value
    return str(reply)


def _summary(to: str, reply: str) -> str:
    return f"{to} replied: {reply[:240]}"
