import json
import subprocess
import sys
from pathlib import Path


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


def test_ask_records_thread_events_and_reply(tmp_path):
    db_path = tmp_path / "agentthread.db"

    result = run_agentthread(
        db_path,
        "ask",
        "--owner",
        "product-dev",
        "--to",
        "prd",
        "--sender",
        "研发侠",
        "--topic",
        "OPE-137 closure criteria",
        "--message",
        "产品是否认可关闭口径？",
        "--artifact",
        '{"type":"multica_issue","id":"OPE-137"}',
        "--mock-reply",
        "认可，但必须等 rotation evidence。",
    )

    assert result["reply"] == "认可，但必须等 rotation evidence。"
    assert result["thread"]["type"] == "consultation"
    assert result["thread"]["owner"] == "product-dev"
    assert result["thread"]["participants"] == ["prd"]
    assert result["thread"]["artifacts"] == [{"type": "multica_issue", "id": "OPE-137"}]
    assert result["outbound_event"]["type"] == "message_sent"
    assert result["inbound_event"]["type"] == "message_received"


def test_task_create_requires_task_backend_and_records_task_thread(tmp_path):
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
        "Please fix login bug",
        check=False,
    )
    assert denied.returncode != 0
    assert "--backend" in denied.stderr

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
        "Please fix login bug",
        "--backend",
        "mock",
    )

    assert result["thread"]["type"] == "task"
    assert result["thread"]["status"] == "waiting_on_participant"
    assert result["thread"]["participants"] == ["product-dev"]
    assert result["thread"]["next_action"] == {"actor": "product-dev", "description": "Please fix login bug"}
    assert result["task_ref"]["backend"] == "mock"
    assert result["event"]["type"] == "task_created"


def test_notify_rejects_agent_targets_and_records_human_notification(tmp_path):
    db_path = tmp_path / "agentthread.db"

    denied = run_agentthread(
        db_path,
        "notify",
        "--owner",
        "prd-bot",
        "--target",
        "product-dev",
        "--message",
        "Please handle this",
        check=False,
    )
    assert denied.returncode != 0
    assert "agent target" in denied.stderr

    result = run_agentthread(
        db_path,
        "notify",
        "--owner",
        "prd-bot",
        "--target",
        "human:ian",
        "--message",
        "OPE-137 口径已确认。",
    )

    assert result["thread"]["type"] == "notification"
    assert result["event"]["type"] == "human_notified"
    assert result["event"]["target"] == "human:ian"


def test_audit_flags_raw_a2a_without_thread(tmp_path):
    db_path = tmp_path / "agentthread.db"
    transcript_dir = tmp_path / "a2a-transcripts"
    transcript_dir.mkdir()
    (transcript_dir / "a2a-raw-test-20260427.jsonl").write_text(
        json.dumps({"sender": "研发侠", "target": "产品侠", "msg": "raw", "reply": "ok"}) + "\n"
    )

    result = run_agentthread(
        db_path,
        "audit",
        "--a2a-transcript-dir",
        str(transcript_dir),
    )

    assert result["status"] == "warn"
    assert result["findings"][0]["code"] == "raw_a2a_without_thread"
    assert "a2a-raw-test-20260427" in result["findings"][0]["sid"]
