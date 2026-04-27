"""Task backend adapter interface and built-in adapters."""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import Any, Callable, Protocol

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


class MulticaTaskBackend:
    name = "multica"

    def __init__(self, runner: Callable[[list[str]], dict[str, Any]] | None = None) -> None:
        self.runner = runner

    def create_task(self, spec: TaskSpec) -> dict[str, Any]:
        cmd = [
            "multica",
            "issue",
            "create",
            "--title",
            spec.topic,
            "--description",
            spec.description,
            "--assignee",
            spec.assignee,
            "--output",
            "json",
        ]
        parent = _first_artifact_id(spec.artifacts, "multica_issue")
        if parent:
            cmd.extend(["--parent", parent])
        runner = self.runner or _run_multica_json
        issue = runner(cmd)
        return {
            "backend": self.name,
            "id": issue.get("id"),
            "identifier": issue.get("identifier"),
            "status": issue.get("status"),
            "assignee": spec.assignee,
            "topic": spec.topic,
        }


BACKENDS: dict[str, TaskBackend] = {
    "mock": MockTaskBackend(),
    "multica": MulticaTaskBackend(),
}


def get_task_backend(name: str) -> TaskBackend:
    try:
        return BACKENDS[name]
    except KeyError:
        raise ValueError(f"No task backend adapter registered for {name!r}") from None


def _run_multica_json(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise ValueError(f"multica command failed: {proc.stderr.strip() or proc.stdout.strip()}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"multica returned non-JSON output: {exc.msg}") from None
    if not isinstance(data, dict):
        raise ValueError("multica returned unexpected JSON shape")
    return data


def _first_artifact_id(artifacts: list[dict[str, Any]], artifact_type: str) -> str | None:
    for artifact in artifacts:
        if artifact.get("type") == artifact_type and artifact.get("id"):
            return str(artifact["id"])
    return None
