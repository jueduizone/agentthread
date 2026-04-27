"""Tiny config helpers for AgentThread workflow CLI.

The project intentionally has no runtime dependencies, so this supports the small
YAML subset emitted by `agentthread init` and used by tests: nested mappings and
lists of scalar strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_CONFIG = """# AgentThread configuration
agents:
  product-agent:
    role: product
    transport: mock
  dev-agent:
    role: engineering
    transport: mock

task_backends:
  mock:
    type: mock

policies:
  allowed_task_backends:
    - mock
  raw_transport_enabled: false
"""


def write_default_config(directory: str | Path, *, overwrite: bool = False) -> Path:
    directory = Path(directory).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "agentthread.yaml"
    if path.exists() and not overwrite:
        return path
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return path


def load_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    config_path = Path(path).expanduser()
    if not config_path.exists():
        raise FileNotFoundError(str(config_path))
    return parse_simple_yaml(config_path.read_text(encoding="utf-8"))


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_at_indent: dict[int, tuple[dict[str, Any], str]] = {}
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            value = _parse_scalar(line[2:].strip())
            if not isinstance(parent, list):
                holder, key = last_key_at_indent[indent - 2]
                new_list: list[Any] = []
                holder[key] = new_list
                parent = new_list
                stack.append((indent - 2, parent))
            parent.append(value)
            continue
        key, sep, value_text = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        value_text = value_text.strip()
        if value_text == "":
            value: Any = {}
        else:
            value = _parse_scalar(value_text)
        parent[key] = value
        if isinstance(value, dict):
            stack.append((indent, value))
            last_key_at_indent[indent] = (parent, key)
        else:
            last_key_at_indent[indent] = (parent, key)
    return root


def allowed_task_backends(config: dict[str, Any]) -> list[str]:
    policies = config.get("policies") or {}
    value = policies.get("allowed_task_backends") or []
    return [str(item) for item in value]


def _parse_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
