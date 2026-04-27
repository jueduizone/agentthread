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


def test_doctor_reports_default_environment_health(tmp_path):
    db_path = tmp_path / "agentthread.db"

    result = run_agentthread(db_path, "doctor")

    assert result["status"] == "ok"
    codes = [check["code"] for check in result["checks"]]
    assert "database_writable" in codes
    assert "policy_loaded" in codes
    assert "raw_transport_disabled" in codes


def test_policy_command_explains_task_vs_consultation_rules(tmp_path):
    db_path = tmp_path / "agentthread.db"

    result = run_agentthread(db_path, "policy")

    assert result["status"] == "ok"
    rule_names = {rule["name"] for rule in result["rules"]}
    assert "tasks_require_backend" in rule_names
    assert "consultation_requires_thread" in rule_names
    assert "human_notify_rejects_agent_targets" in rule_names
    assert "raw_transport_disabled_by_default" in rule_names


def test_audit_flags_stale_open_thread(tmp_path):
    db_path = tmp_path / "agentthread.db"
    created = run_agentthread(
        db_path,
        "task",
        "create",
        "--owner",
        "prd-bot",
        "--assignee",
        "product-dev",
        "--topic",
        "Stale task",
        "--description",
        "Do this",
        "--backend",
        "mock",
    )

    result = run_agentthread(db_path, "audit", "--stale-hours", "0")

    assert result["status"] == "warn"
    assert any(
        finding["code"] == "stale_active_thread" and finding["thread_id"] == created["thread"]["thread_id"]
        for finding in result["findings"]
    )


def test_task_create_allows_configured_backend_only(tmp_path):
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
        "Fix bug",
        "--description",
        "Fix bug",
        "--backend",
        "github",
        "--allowed-task-backend",
        "mock",
        check=False,
    )

    assert denied.returncode != 0
    assert "not allowed by policy" in denied.stderr
