"""Basic owner-first recall for vague follow-up questions."""

from __future__ import annotations

import re
from typing import Any

from .store import ACTIVE_STATUSES, Store


def answer_context(
    store: Store,
    *,
    owner: str,
    query: str,
    source: dict[str, Any] | None = None,
    participant_hint: str | None = None,
    topic_hint: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    candidates = store.recent_threads(owner=owner, limit=100)
    scored = []
    query_terms = _terms(query)
    hint_terms = _terms(topic_hint or "")

    for thread in candidates:
        score = 0.15
        active = thread["status"] in ACTIVE_STATUSES
        if active:
            score += 0.2
        if source and _same_source(thread.get("source"), source):
            score += 0.5 if active else 0.25
        if participant_hint and participant_hint in thread.get("participants", []):
            score += 0.25

        text = " ".join(
            str(part or "")
            for part in (
                thread.get("topic"),
                thread.get("latest_summary"),
                " ".join(thread.get("participants", [])),
                " ".join(thread.get("tags", [])),
            )
        ).lower()
        keyword_hits = sum(1 for term in query_terms | hint_terms if term and term in text)
        score += min(keyword_hits * 0.08, 0.24)
        if topic_hint and topic_hint.lower() in text:
            score += 0.2

        compact = {
            "thread_id": thread["thread_id"],
            "type": thread["type"],
            "status": thread["status"],
            "topic": thread["topic"],
            "owner": thread["owner"],
            "participants": thread["participants"],
            "latest_summary": thread["latest_summary"],
            "next_action": thread["next_action"],
            "artifacts": thread["artifacts"],
            "updated_at": thread["updated_at"],
            "confidence": round(min(score, 0.99), 2),
        }
        scored.append((score, thread["updated_at"], compact))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:limit]]


def _same_source(left: dict[str, Any] | None, right: dict[str, Any]) -> bool:
    if not left:
        return False
    if right.get("platform") is not None and left.get("platform") != right.get("platform"):
        return False
    if right.get("chat_id") is not None and str(left.get("chat_id")) != str(right.get("chat_id")):
        return False
    if right.get("session_id") is not None and left.get("session_id") != right.get("session_id"):
        return False
    return True


def _terms(text: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]+", text) if len(term) > 1}
