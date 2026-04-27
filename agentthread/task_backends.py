"""Task backend adapter interface and built-in adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .ids import new_id


@dataclass(frozen=True)
class TaskSpec:
    owner: str
    assignee: str
    topic: str
    description: str
    artifacts: list[dict[str, Any]]


class TaskBackend(Protocol):
    name: str

    def create_task(self, spec: TaskSpec) -> dict[str, Any]:
        ...


class MockTaskBackend:
    name = "mock"

    def create_task(self, spec: TaskSpec) -> dict[str, Any]:
        return {
            "backend": self.name,
            "id": new_id("mock-task"),
            "status": "created",
            "owner": spec.owner,
            "assignee": spec.assignee,
            "topic": spec.topic,
        }


BACKENDS: dict[str, TaskBackend] = {
    "mock": MockTaskBackend(),
}


def get_task_backend(name: str) -> TaskBackend:
    try:
        return BACKENDS[name]
    except KeyError:
        raise ValueError(f"No task backend adapter registered for {name!r}") from None
