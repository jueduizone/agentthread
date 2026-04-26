import sqlite3

import pytest

from agentthread.store import Store


def test_create_update_events_inbox_and_recent_threads(tmp_path):
    db_path = tmp_path / "agentthread.db"
    store = Store(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000

    thread = store.create_thread(
        type="task",
        owner="prd-bot",
        participants=["product-dev"],
        topic="HackAgent QA accounts",
        created_by={"type": "human", "id": "ian"},
        source={"platform": "telegram", "chat_id": "409747388"},
        latest_summary="Ian asked Product Agent to get Dev Agent to create accounts.",
        tags=["hackagent", "qa"],
    )

    assert thread["thread_id"].startswith("thr_")
    assert thread["status"] == "open"
    assert thread["participants"] == ["product-dev"]
    assert thread["created_at"] == thread["updated_at"]

    fetched = store.get_thread(thread["thread_id"])
    assert fetched == thread

    updated = store.update_thread(
        thread["thread_id"],
        status="waiting_on_participant",
        latest_summary="Dev Agent is creating six QA accounts.",
        next_action={"actor": "product-dev", "description": "Create accounts"},
        artifacts=[{"type": "multica_issue", "id": "OPE-105"}],
    )
    assert updated["status"] == "waiting_on_participant"
    assert updated["next_action"]["actor"] == "product-dev"
    assert updated["artifacts"][0]["id"] == "OPE-105"
    assert updated["updated_at"] >= thread["updated_at"]

    event = store.append_event(
        thread["thread_id"],
        type="message_sent",
        actor="prd-bot",
        target="product-dev",
        summary="Asked Dev Agent to create QA accounts.",
        content="Please create six QA accounts for HackAgent testing.",
        transport={"kind": "a2a_gateway"},
    )
    assert event["event_id"].startswith("evt_")
    assert event["thread_id"] == thread["thread_id"]
    assert store.list_events(thread["thread_id"]) == [event]

    inbox = store.create_inbox_item(
        agent="product-dev",
        thread_id=thread["thread_id"],
        kind="assignment",
        summary="Product Agent assigned HackAgent QA accounts to you.",
    )
    assert inbox["inbox_id"].startswith("inb_")
    assert inbox["read"] is False
    assert store.list_inbox("product-dev") == [inbox]

    marked = store.mark_inbox_read(inbox["inbox_id"])
    assert marked["read"] is True
    assert store.list_inbox("product-dev", unread_only=True) == []

    recent = store.recent_threads(
        owner="prd-bot",
        source={"platform": "telegram", "chat_id": "409747388"},
        statuses=["waiting_on_participant"],
    )
    assert [item["thread_id"] for item in recent] == [thread["thread_id"]]


def test_store_returns_none_for_missing_records(tmp_path):
    store = Store(tmp_path / "agentthread.db")

    assert store.get_thread("thr_missing") is None
    assert store.mark_inbox_read("inb_missing") is None


def test_duplicate_thread_id_raises_value_error(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    store.create_thread(
        thread_id="thr_fixed",
        type="task",
        owner="prd-bot",
        topic="Original",
    )

    with pytest.raises(ValueError, match="Duplicate thread_id"):
        store.create_thread(
            thread_id="thr_fixed",
            type="task",
            owner="prd-bot",
            topic="Duplicate",
        )


def test_unknown_foreign_keys_raise_key_error(tmp_path):
    store = Store(tmp_path / "agentthread.db")

    with pytest.raises(KeyError, match="Unknown thread_id"):
        store.append_event("thr_missing", type="message_sent")

    with pytest.raises(KeyError, match="Unknown thread_id"):
        store.create_inbox_item(
            agent="product-dev",
            thread_id="thr_missing",
            kind="assignment",
            summary="Missing thread",
        )


def test_json_roundtrip_for_metadata_and_artifacts(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    thread = store.create_thread(
        type="task",
        owner="prd-bot",
        topic="Structured payloads",
        artifacts=[
            {"type": "github_issue", "id": 42, "labels": ["bug", "p0"]},
        ],
        metadata={"priority": 1, "nested": {"ok": True}},
    )
    event = store.append_event(
        thread["thread_id"],
        type="artifact_linked",
        artifact_refs=[{"type": "github_issue", "id": 42}],
        metadata={"confidence": 0.91, "reviewers": ["ian"]},
    )
    inbox = store.create_inbox_item(
        agent="product-dev",
        thread_id=thread["thread_id"],
        kind="assignment",
        summary="Structured inbox",
        metadata={"attempts": 2, "flags": {"urgent": True}},
    )

    fetched = store.get_thread(thread["thread_id"])
    assert fetched["artifacts"] == [{"type": "github_issue", "id": 42, "labels": ["bug", "p0"]}]
    assert fetched["metadata"] == {"priority": 1, "nested": {"ok": True}}
    assert store.list_events(thread["thread_id"])[0]["metadata"] == event["metadata"]
    assert store.list_inbox("product-dev")[0]["metadata"] == inbox["metadata"]


def test_recent_threads_ranks_closed_and_done_below_active_threads(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    active = store.create_thread(type="task", owner="prd-bot", topic="Active")
    done = store.create_thread(type="task", owner="prd-bot", topic="Done")
    store.update_thread(done["thread_id"], status="done", closed_at="2026-04-26T00:00:00Z")

    recent = store.recent_threads(owner="prd-bot")

    assert [item["thread_id"] for item in recent] == [active["thread_id"], done["thread_id"]]


def test_export_thread_returns_thread_and_events(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    thread = store.create_thread(type="task", owner="prd-bot", topic="Export me")
    event = store.append_event(thread["thread_id"], type="message_received", summary="Got it")

    exported = store.export_thread(thread["thread_id"])

    assert exported == {"thread": store.get_thread(thread["thread_id"]), "events": [event]}


def test_export_thread_unknown_id_raises_key_error(tmp_path):
    store = Store(tmp_path / "agentthread.db")

    with pytest.raises(KeyError, match="Unknown thread_id"):
        store.export_thread("thr_missing")
