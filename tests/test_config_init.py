import json
import subprocess
import sys
from pathlib import Path


def run_agentthread(db_path, *args, cwd=None, check=True):
    proc = subprocess.run(
        [sys.executable, "-m", "agentthread.workflow_cli", "--db", str(db_path), *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    if check:
        return json.loads(proc.stdout)
    return proc


def test_init_writes_default_config_and_doctor_reads_it(tmp_path):
    db_path = tmp_path / "agentthread.db"

    result = run_agentthread(db_path, "init", "--dir", str(tmp_path))

    config_path = tmp_path / "agentthread.yaml"
    assert result["status"] == "ok"
    assert result["config_path"] == str(config_path)
    assert config_path.exists()
    text = config_path.read_text()
    assert "agents:" in text
    assert "task_backends:" in text
    assert "policies:" in text

    doctor = run_agentthread(db_path, "doctor", "--config", str(config_path))
    assert doctor["status"] == "ok"
    codes = {check["code"] for check in doctor["checks"]}
    assert "config_loaded" in codes
    assert "agents_configured" in codes
    assert "task_backends_configured" in codes


def test_task_create_uses_allowed_backends_from_config(tmp_path):
    db_path = tmp_path / "agentthread.db"
    config_path = tmp_path / "agentthread.yaml"
    config_path.write_text(
        """
agents:
  product-agent:
    role: product
  dev-agent:
    role: engineering
task_backends:
  mock:
    type: mock
policies:
  allowed_task_backends:
    - mock
""".strip()
    )

    denied = run_agentthread(
        db_path,
        "task",
        "create",
        "--config",
        str(config_path),
        "--owner",
        "product-agent",
        "--assignee",
        "dev-agent",
        "--topic",
        "Fix bug",
        "--description",
        "Fix it",
        "--backend",
        "github",
        check=False,
    )
    assert denied.returncode != 0
    assert "not allowed by policy" in denied.stderr

    ok = run_agentthread(
        db_path,
        "task",
        "create",
        "--config",
        str(config_path),
        "--owner",
        "product-agent",
        "--assignee",
        "dev-agent",
        "--topic",
        "Fix bug",
        "--description",
        "Fix it",
        "--backend",
        "mock",
    )
    assert ok["thread"]["owner"] == "product-agent"
    assert ok["task_ref"]["backend"] == "mock"
