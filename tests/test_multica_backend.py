from agentthread.task_backends import MulticaTaskBackend, TaskSpec


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        return {
            "id": "issue-123",
            "identifier": "OPE-999",
            "title": "Fix login bug",
            "status": "todo",
            "assignee_id": "agent-1",
        }


def test_multica_backend_creates_issue_ref():
    runner = FakeRunner()
    backend = MulticaTaskBackend(runner=runner)

    result = backend.create_task(
        TaskSpec(
            owner="prd-bot",
            assignee="研发侠",
            topic="Fix login bug",
            description="Fix login bug",
            artifacts=[{"type": "multica_issue", "id": "OPE-1"}],
        )
    )

    assert result == {
        "backend": "multica",
        "id": "issue-123",
        "identifier": "OPE-999",
        "status": "todo",
        "assignee": "研发侠",
        "topic": "Fix login bug",
    }
    assert runner.calls == [
        [
            "multica",
            "issue",
            "create",
            "--title",
            "Fix login bug",
            "--description",
            "Fix login bug",
            "--assignee",
            "研发侠",
            "--output",
            "json",
            "--parent",
            "OPE-1",
        ]
    ]
