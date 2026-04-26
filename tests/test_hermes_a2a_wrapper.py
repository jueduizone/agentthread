import sys
import types

import pytest

from agentthread.store import Store


def test_send_threaded_a2a_creates_thread_events_inbox_and_updates_state(tmp_path):
    from agentthread.integrations.hermes import send_threaded_a2a

    store = Store(tmp_path / "agentthread.db")
    calls = []

    def fake_send_func(**kwargs):
        calls.append(kwargs)
        return "I can handle this. " + ("x" * 260)

    result = send_threaded_a2a(
        store,
        owner="prd-bot",
        to="dev",
        topic="QA accounts",
        message="Please create six QA accounts.",
        send_func=fake_send_func,
        sid="a2a-qa-accounts",
        sender="产品侠",
        source={"platform": "telegram", "chat_id": "409747388"},
        artifacts=[{"type": "linear_issue", "id": "AT-1"}],
        metadata={"priority": 1},
        next_action={"actor": "prd-bot", "description": "Tell Ian what Dev said."},
    )

    assert calls == [
        {
            "to": "dev",
            "sid": "a2a-qa-accounts",
            "sender": "产品侠",
            "msg": "Please create six QA accounts.",
        }
    ]

    thread = result["thread"]
    assert thread["thread_id"].startswith("thr_")
    assert thread["owner"] == "prd-bot"
    assert thread["participants"] == ["dev"]
    assert thread["type"] == "consultation"
    assert thread["status"] == "answered"
    assert thread["topic"] == "QA accounts"
    assert thread["source"] == {"platform": "telegram", "chat_id": "409747388"}
    assert thread["artifacts"] == [{"type": "linear_issue", "id": "AT-1"}]
    assert thread["metadata"] == {"priority": 1}
    assert thread["next_action"] == {"actor": "prd-bot", "description": "Tell Ian what Dev said."}
    assert thread["latest_summary"] == "dev replied: " + result["reply"][:240]

    outbound = result["outbound_event"]
    inbound = result["inbound_event"]
    assert outbound["type"] == "message_sent"
    assert outbound["actor"] == "产品侠"
    assert outbound["target"] == "dev"
    assert outbound["content"] == "Please create six QA accounts."
    assert outbound["transport"] == {
        "kind": "hermes_a2a",
        "sid": "a2a-qa-accounts",
        "to": "dev",
    }
    assert inbound["type"] == "message_received"
    assert inbound["actor"] == "dev"
    assert inbound["target"] == "prd-bot"
    assert inbound["content"] == result["reply"]

    assert result["inbox_item"]["agent"] == "dev"
    assert result["inbox_item"]["thread_id"] == thread["thread_id"]
    assert store.list_events(thread["thread_id"]) == [outbound, inbound]
    assert store.list_inbox("dev") == [result["inbox_item"]]


def test_send_threaded_a2a_reuses_existing_thread_without_inbox(tmp_path):
    from agentthread.integrations.hermes import send_threaded_a2a

    store = Store(tmp_path / "agentthread.db")
    existing = store.create_thread(
        type="task",
        owner="prd-bot",
        participants=["dev"],
        topic="Existing task",
        status="waiting_on_owner",
    )

    result = send_threaded_a2a(
        store,
        owner="prd-bot",
        to="dev",
        topic="Ignored when thread exists",
        message="Any update?",
        send_func=lambda **kwargs: "Done.",
        thread_id=existing["thread_id"],
        sid="a2a-existing",
        create_inbox=True,
    )

    assert "inbox_item" not in result
    assert result["thread"]["thread_id"] == existing["thread_id"]
    assert result["thread"]["topic"] == "Existing task"
    assert result["thread"]["status"] == "answered"
    assert store.list_inbox("dev") == []


def test_send_threaded_a2a_unknown_thread_id_raises_key_error(tmp_path):
    from agentthread.integrations.hermes import send_threaded_a2a

    store = Store(tmp_path / "agentthread.db")

    with pytest.raises(KeyError, match="Unknown thread_id"):
        send_threaded_a2a(
            store,
            owner="prd-bot",
            to="dev",
            topic="Missing",
            message="Hello",
            send_func=lambda **kwargs: "unused",
            thread_id="thr_missing",
        )


def test_send_threaded_a2a_uses_owner_as_default_sender_and_no_inbox_when_disabled(tmp_path):
    from agentthread.integrations.hermes import send_threaded_a2a

    store = Store(tmp_path / "agentthread.db")
    calls = []

    result = send_threaded_a2a(
        store,
        owner="prd-bot",
        to="dev",
        topic="No inbox",
        message="Hello",
        send_func=lambda **kwargs: calls.append(kwargs) or {"content": "Structured reply"},
        create_inbox=False,
    )

    assert calls[0]["sender"] == "prd-bot"
    assert result["reply"] == "Structured reply"
    assert "inbox_item" not in result
    assert store.list_inbox("dev") == []


def test_make_a2a_send_func_imports_a2a_send_lazily(monkeypatch, tmp_path):
    from agentthread.integrations.hermes import make_a2a_send_func

    module = types.ModuleType("a2a_send")
    calls = []

    def send_a2a_message(to, sid, sender, msg):
        calls.append({"to": to, "sid": sid, "sender": sender, "msg": msg})
        return "Hermes reply"

    module.send_a2a_message = send_a2a_message
    monkeypatch.setitem(sys.modules, "a2a_send", module)
    original_path = list(sys.path)

    send_func = make_a2a_send_func(script_path=tmp_path)
    assert sys.path == original_path
    assert send_func(to="dev", sid="a2a-test", sender="prd-bot", msg="Ping") == "Hermes reply"
    assert calls == [{"to": "dev", "sid": "a2a-test", "sender": "prd-bot", "msg": "Ping"}]
