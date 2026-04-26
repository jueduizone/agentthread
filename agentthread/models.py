"""Small stdlib data models for AgentThread records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


JsonDict = dict[str, Any]


@dataclass
class Thread:
    thread_id: str
    type: str
    status: str
    topic: str
    owner: str
    participants: list[str] = field(default_factory=list)
    created_by: JsonDict = field(default_factory=dict)
    source: JsonDict | None = None
    latest_summary: str | None = None
    next_action: JsonDict | None = None
    artifacts: list[JsonDict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    closed_at: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class Event:
    event_id: str
    thread_id: str
    type: str
    actor: str | None = None
    target: str | None = None
    summary: str | None = None
    content: str | None = None
    transport: JsonDict | None = None
    artifact_refs: list[JsonDict] = field(default_factory=list)
    created_at: str = ""
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class InboxItem:
    inbox_id: str
    agent: str
    thread_id: str
    kind: str
    summary: str
    read: bool = False
    created_at: str = ""
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)
