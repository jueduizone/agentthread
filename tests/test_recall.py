from agentthread.recall import answer_context
from agentthread.store import Store


def test_answer_context_prefers_same_source_active_thread(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    same_source = store.create_thread(
        type="task",
        owner="prd-bot",
        participants=["product-dev"],
        topic="HackAgent QA accounts",
        source={"platform": "telegram", "chat_id": "409747388"},
        latest_summary="Dev Agent is creating QA accounts.",
        next_action={"actor": "product-dev", "description": "Update OPE-105"},
        artifacts=[{"type": "multica_issue", "id": "OPE-105"}],
    )
    store.update_thread(same_source["thread_id"], status="waiting_on_participant")

    other_source = store.create_thread(
        type="task",
        owner="prd-bot",
        participants=["media"],
        topic="Announcement draft",
        source={"platform": "telegram", "chat_id": "other"},
        latest_summary="Media is drafting announcement copy.",
    )
    store.update_thread(other_source["thread_id"], status="in_progress")

    matches = answer_context(
        store,
        owner="prd-bot",
        query="进展怎么样",
        source={"platform": "telegram", "chat_id": "409747388"},
    )

    assert matches[0]["thread_id"] == same_source["thread_id"]
    assert matches[0]["confidence"] > matches[1]["confidence"]
    assert matches[0]["next_action"]["actor"] == "product-dev"
    assert matches[0]["artifacts"][0]["id"] == "OPE-105"


def test_answer_context_uses_participant_and_topic_hints(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    product = store.create_thread(
        type="consultation",
        owner="product-dev",
        participants=["prd-bot"],
        topic="Billing priority decision",
        latest_summary="Product says billing is P0.",
    )
    media = store.create_thread(
        type="consultation",
        owner="product-dev",
        participants=["media"],
        topic="Launch copy review",
        latest_summary="Media reviewed launch copy.",
    )

    matches = answer_context(
        store,
        owner="product-dev",
        query="产品怎么说 billing",
        participant_hint="prd-bot",
        topic_hint="billing",
    )

    assert matches[0]["thread_id"] == product["thread_id"]
    assert {item["thread_id"] for item in matches} == {
        product["thread_id"],
        media["thread_id"],
    }


def test_answer_context_limits_results_and_ignores_other_owners(tmp_path):
    store = Store(tmp_path / "agentthread.db")
    for idx in range(3):
        store.create_thread(
            type="task",
            owner="prd-bot",
            participants=["product-dev"],
            topic=f"Owned task {idx}",
            latest_summary=f"Owned summary {idx}",
        )
    store.create_thread(
        type="task",
        owner="media",
        participants=["product-dev"],
        topic="Other owner task",
        latest_summary="Should not be returned.",
    )

    matches = answer_context(store, owner="prd-bot", query="progress", limit=2)

    assert len(matches) == 2
    assert all(item["owner"] == "prd-bot" for item in matches)
