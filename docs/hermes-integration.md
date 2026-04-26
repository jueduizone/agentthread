# Hermes Integration

AgentThread can wrap a Hermes A2A send so the transport call and the collaboration state stay in sync.

The integration is optional. AgentThread does not import Hermes modules at package import time, and runtime code stays on the Python standard library.

## Owner Semantics

`owner` is the agent responsible for the user-facing thread. It is not necessarily the same as the Hermes sender display name.

For example, if `prd-bot` receives a user request and asks `dev` for help:

```text
owner = "prd-bot"
to = "dev"
sender = "产品侠"
```

The owner remains `prd-bot` because that agent must answer later follow-ups such as "progress?". Hermes receives `sender` for transport display identity. If `sender` is omitted, AgentThread uses `owner`.

## Injected Send Function

`send_threaded_a2a` calls the injected function with keyword arguments:

```python
send_func(to=to, sid=effective_sid, sender=effective_sender, msg=message)
```

`effective_sid` is the provided `sid`, or the AgentThread `thread_id` when `sid` is omitted.

## Usage With an Injected Callable

```python
from agentthread.store import Store
from agentthread.integrations.hermes import send_threaded_a2a

store = Store("agentthread.db")

def send_func(*, to, sid, sender, msg):
    # Call your transport here.
    return "I can handle this."

result = send_threaded_a2a(
    store,
    owner="prd-bot",
    to="dev",
    topic="QA accounts",
    message="Please create six QA accounts for testing.",
    send_func=send_func,
    sid="a2a-qa-accounts",
    sender="产品侠",
    source={"platform": "telegram", "chat_id": "409747388"},
    artifacts=[{"type": "linear_issue", "id": "AT-1"}],
    next_action={"actor": "prd-bot", "description": "Report Dev's answer to the user."},
)
```

When no `thread_id` is provided, the wrapper creates a thread with:

- `owner` as the owner;
- `to` as the participant;
- `status_before`, defaulting to `waiting_on_participant`;
- optional `source`, `artifacts`, and `metadata`;
- an unread inbox item for the participant, unless `create_inbox=False`.

It appends a `message_sent` event before calling the transport, then appends a `message_received` event with the reply. Finally it updates the thread to `status_after`, defaulting to `answered`, and writes a deterministic `latest_summary`:

```text
{to} replied: {first 240 characters of reply}
```

## Usage With Local Hermes

If the local Hermes A2A script exists at `~/.hermes/skills/productivity/a2a-chat/scripts/a2a_send.py`, use the lazy adapter:

```python
from agentthread.store import Store
from agentthread.integrations.hermes import make_a2a_send_func, send_threaded_a2a

store = Store()
send_func = make_a2a_send_func()

result = send_threaded_a2a(
    store,
    owner="prd-bot",
    to="dev",
    topic="Architecture check",
    message="Can you review whether this approach is feasible?",
    send_func=send_func,
    sid="a2a-architecture-check",
    sender="产品侠",
)
```

`make_a2a_send_func()` temporarily adds the Hermes script directory to `sys.path`, imports `a2a_send.send_a2a_message`, and returns a callable using the wrapper signature above.

## Reusing a Thread

Pass `thread_id` to append another A2A turn to an existing thread:

```python
send_threaded_a2a(
    store,
    owner="prd-bot",
    to="dev",
    topic="Ignored for existing threads",
    message="Any update?",
    send_func=send_func,
    thread_id="thr_existing",
)
```

If the thread does not exist, `KeyError` is raised. Inbox items are only created for newly-created threads.
