"""Policy primitives for AgentThread high-level workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyRule:
    name: str
    description: str
    level: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "level": self.level}


DEFAULT_RULES = [
    PolicyRule("tasks_require_backend", "Work delegation must use an explicit task backend."),
    PolicyRule("consultation_requires_thread", "Agent consultation must create or update an AgentThread."),
    PolicyRule("human_notify_rejects_agent_targets", "Human notifications cannot target agents."),
    PolicyRule("raw_transport_disabled_by_default", "Raw transport is for diagnostics only; high-level workflows are preferred."),
]


def default_policy() -> dict[str, Any]:
    return {"status": "ok", "rules": [rule.to_dict() for rule in DEFAULT_RULES]}


def ensure_backend_allowed(backend: str, allowed_backends: list[str] | None) -> None:
    if allowed_backends and backend not in allowed_backends:
        allowed = ", ".join(allowed_backends)
        raise ValueError(f"backend {backend!r} is not allowed by policy; allowed backends: {allowed}")
