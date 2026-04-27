import json
import subprocess
import sys


def run_agentthread(db_path, *args, check=True):
    proc = subprocess.run(
        [sys.executable, "-m", "agentthread.workflow_cli", "--db", str(db_path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    if check:
        return json.loads(proc.stdout)
    return proc


def test_mock_task_backend_returns_stable_task_ref(tmp_path):
    db_path = tmp_path / "agentthread.db"

    result = run_agentthread(
        db_path,
        "task",
        "create",
        "--owner",
        "prd-bot",
        "--assignee",
        "product-dev",
        "--topic",
        "Fix login bug",
        "--description",
        "Fix login bug",
        "--backend",
        "mock",
    )

    task_ref = result["task_ref"]
    assert task_ref["backend"] == "mock"
    assert task_ref["id"].startswith("mock-task_")
    assert task_ref["status"] == "created"
    assert task_ref["assignee"] == "product-dev"
    assert task_ref["topic"] == "Fix login bug"
    assert result["thread"]["artifacts"][-1]["id"] == task_ref["id"]


def test_unsupported_backend_fails_until_adapter_exists(tmp_path):
    db_path = tmp_path / "agentthread.db"

    denied = run_agentthread(
        db_path,
        "task",
        "create",
        "--owner",
        "prd-bot",
        "--assignee",
        "product-dev",
        "--topic",
        "Fix login bug",
        "--description",
        "Fix login bug",
        "--backend",
        "linear",
        check=False,
    )

    assert denied.returncode != 0
    assert "No task backend adapter" in denied.stderr
