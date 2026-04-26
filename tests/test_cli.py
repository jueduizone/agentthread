import json
import subprocess
import sys

from agentthread.store import Store


def run_cli(db_path, *args):
    proc = subprocess.run(
        [sys.executable, "-m", "agentthread.cli", "--db", str(db_path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(proc.stdout)


def test_cli_create_update_event_recent_and_answer_context(tmp_path):
    db_path = tmp_path / "agentthread.db"

    created = run_cli(
        db_path,
        "create",
        "--type",
        "task",
        "--owner",
        "prd-bot",
        "--participant",
        "product-dev",
        "--created-by",
        "ian",
        "--source-platform",
        "telegram",
        "--source-chat",
        "409747388",
        "--topic",
        "HackAgent QA accounts",
        "--summary",
        "Ian asked Product Agent to get Dev Agent to create QA accounts.",
    )
    thread_id = created["thread_id"]
    assert thread_id.startswith("thr_")

    updated = run_cli(
        db_path,
        "update",
        thread_id,
        "--status",
        "waiting_on_participant",
        "--next-actor",
        "product-dev",
        "--next-action",
        "Create accounts and update issue",
        "--summary",
        "Dev Agent is creating QA accounts.",
    )
    assert updated["next_action"]["description"] == "Create accounts and update issue"

    event = run_cli(
        db_path,
        "event",
        "append",
        thread_id,
        "--type",
        "message_sent",
        "--actor",
        "prd-bot",
        "--target",
        "product-dev",
        "--summary",
        "Asked Dev Agent to create QA accounts.",
        "--content",
        "Please create six QA accounts.",
    )
    assert event["thread_id"] == thread_id

    recent = run_cli(
        db_path,
        "recent",
        "--owner",
        "prd-bot",
        "--source-platform",
        "telegram",
        "--source-chat",
        "409747388",
    )
    assert [item["thread_id"] for item in recent] == [thread_id]

    context = run_cli(
        db_path,
        "answer-context",
        "--owner",
        "prd-bot",
        "--query",
        "进展怎么样",
        "--source-platform",
        "telegram",
        "--source-chat",
        "409747388",
    )
    assert context[0]["thread_id"] == thread_id
    assert context[0]["confidence"] > 0.8


def test_cli_get_events_export_and_json_payloads(tmp_path):
    db_path = tmp_path / "agentthread.db"

    created = run_cli(
        db_path,
        "create",
        "--type",
        "task",
        "--owner",
        "prd-bot",
        "--participant",
        "product-dev",
        "--topic",
        "Structured CLI payloads",
        "--json",
        json.dumps(
            {
                "created_by": {"type": "human", "id": "ian", "display_name": "Ian"},
                "source": {"platform": "telegram", "chat_id": "409747388"},
                "next_action": {"actor": "product-dev", "description": "Reply"},
                "artifacts": [{"type": "linear_issue", "id": "AT-1"}],
                "tags": ["agentthread", "qa"],
                "metadata": {"priority": 1},
            }
        ),
    )
    thread_id = created["thread_id"]
    assert created["created_by"]["display_name"] == "Ian"
    assert created["source"]["platform"] == "telegram"
    assert created["next_action"]["actor"] == "product-dev"
    assert created["artifacts"][0]["id"] == "AT-1"
    assert created["tags"] == ["agentthread", "qa"]
    assert created["metadata"] == {"priority": 1}

    fetched = run_cli(db_path, "get", thread_id)
    assert fetched["thread_id"] == thread_id

    updated = run_cli(
        db_path,
        "update",
        thread_id,
        "--json",
        json.dumps(
            {
                "next_action": {"actor": "prd-bot", "description": "Follow up"},
                "artifacts": [{"type": "github_pr", "id": 7}],
                "tags": ["followup"],
                "metadata": {"priority": 2},
            }
        ),
    )
    assert updated["next_action"]["actor"] == "prd-bot"
    assert updated["artifacts"] == [{"type": "github_pr", "id": 7}]
    assert updated["tags"] == ["followup"]
    assert updated["metadata"] == {"priority": 2}

    event = run_cli(
        db_path,
        "event",
        "append",
        thread_id,
        "--type",
        "message_received",
        "--summary",
        "Dev replied.",
    )

    events = run_cli(db_path, "events", thread_id)
    assert events == [event]

    current_thread = run_cli(db_path, "get", thread_id)
    exported = run_cli(db_path, "export", thread_id)
    assert exported == {"thread": current_thread, "events": [event]}


def test_cli_inbox_list_and_read(tmp_path):
    db_path = tmp_path / "agentthread.db"
    store = Store(db_path)
    thread = store.create_thread(type="task", owner="prd-bot", topic="Inbox CLI")
    inbox = store.create_inbox_item(
        agent="product-dev",
        thread_id=thread["thread_id"],
        kind="assignment",
        summary="Please handle this",
    )

    items = run_cli(db_path, "inbox", "list", "--agent", "product-dev")
    assert items == [inbox]

    marked = run_cli(db_path, "inbox", "read", inbox["inbox_id"])
    assert marked["inbox_id"] == inbox["inbox_id"]
    assert marked["read"] is True
