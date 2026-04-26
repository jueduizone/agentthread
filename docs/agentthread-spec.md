# AgentThread Spec

> Working draft for an open-source collaboration state layer for multi-agent systems.

## 1. Problem

Modern agent systems often have multiple long-running agents connected to different entry points: Telegram bots, Slack apps, Discord bots, webhook workers, CLI sessions, API servers, cron jobs, and internal task runners.

The transport layer can usually deliver a message somewhere, but real coordination still breaks down because each entry point creates separate sessions and memories.

Example failure mode:

```text
Ian ↔ Product Agent: "Please ask Dev Agent to handle A."
Product Agent ↔ Dev Agent: talks through A2A/API/group mirror.
Ian ↔ Product Agent later: "How is it going?"
Product Agent: does not know which task, what Dev Agent replied, or current status.
```

This is not mainly a messaging problem. It is a **collaboration state** problem.

Agents need a shared, persistent, queryable object that records:

- who owns the work;
- who was asked to help;
- what the user originally wanted;
- what was sent between agents;
- what the latest status is;
- what the next action is;
- where supporting artifacts live;
- how to recover context when the user asks a vague follow-up like "progress?".

## 2. One-sentence positioning

**AgentThread is a lightweight ownership and state layer for cross-agent collaboration.**

A2A lets agents talk. AgentThread lets agents remember who is responsible, what happened, and what to do next.

## 3. Non-goals

AgentThread is **not**:

- a replacement for A2A protocol;
- a new IM platform;
- a universal agent runtime;
- a vector memory product;
- a task manager UI first;
- a transport-only relay.

It can integrate with A2A, Telegram, Slack, Discord, webhooks, Multica, Linear, GitHub Issues, or local files, but its core abstraction is the collaboration thread.

## 4. Core idea

Every cross-agent collaboration creates or updates a **Thread**.

A Thread is the source of truth for:

```text
owner agent → peer/assignee agent(s) → state updates → user follow-up recall
```

The owner is the agent that received the user's request and is responsible for answering future follow-ups.

Examples:

```text
Ian asks Product Agent to ask Dev Agent to fix QA accounts.
owner = Product Agent
participants = [Dev Agent]
type = task
status = waiting_on_dev
```

```text
Ian asks Dev Agent to ask Product Agent for priority judgment.
owner = Dev Agent
participants = [Product Agent]
type = consultation
status = answered
```

Direction does not matter. Ownership does.

## 5. Terminology

### Agent

A named autonomous or semi-autonomous worker.

Examples:

- `prd-bot`
- `product-dev`
- `media`
- `qa-agent`
- `docs-agent`

### User

A human or upstream system that asks an agent to do something.

### Owner

The agent responsible for the thread. The owner must be able to answer user follow-ups.

### Participant

An agent or external actor involved in the thread.

### Thread

A durable collaboration object. It stores state, metadata, transcript references, artifacts, and next actions.

### Event

An append-only record inside a thread: created, message sent, response received, status changed, artifact linked, etc.

### Transport

A mechanism used to notify or call another agent. Examples: HTTP, webhook, A2A JSON-RPC, Telegram, Slack, Discord, file inbox.

### Artifact

An external durable object related to the thread: Multica issue, Linear ticket, GitHub issue, transcript file, PR, document, log, etc.

## 6. Design principles

1. **State over transport**  
   Transport is replaceable. Thread state is the source of truth.

2. **Owner-first recall**  
   The owner agent must be able to answer "progress?" by querying recent owned threads.

3. **Append-only event log**  
   Thread history should be reconstructable and auditable.

4. **Cross-IM by design**  
   Telegram, Slack, Discord, Feishu, Matrix, CLI, and webhooks should be adapters, not core assumptions.

5. **No bot-to-bot dependency**  
   Some IMs, especially Telegram, do not reliably deliver bot-to-bot messages. AgentThread must work without bot-to-bot messaging.

6. **Human-readable fallback**  
   JSON is the API format, but the state should be easy to inspect manually.

7. **Local-first MVP**  
   Start with SQLite or JSONL. Add server mode later.

8. **Task systems are artifacts, not competitors**  
   Multica, Linear, GitHub Issues, and Jira can be linked as artifacts. AgentThread tracks ownership and recall across them.

## 7. Thread types

### `task`

A participant is expected to do work and update status.

Examples:

- "Ask Dev Agent to create test accounts."
- "Have Media Agent draft the announcement."
- "Tell Product Agent to clarify priority."

### `consultation`

A participant is expected to provide advice, review, or opinion.

Examples:

- "Ask Dev Agent whether this architecture is feasible."
- "Ask Product Agent how to prioritize this."

### `handoff`

Responsibility moves from one owner to another.

Example:

- Product Agent starts discovery, then transfers ownership to Dev Agent for implementation.

### `notification`

No action required, but a participant should be aware.

Example:

- "Tell Dev Agent that QA is blocked by login issue."

## 8. Thread statuses

Recommended base statuses:

```text
open
waiting_on_owner
waiting_on_participant
in_progress
blocked
answered
done
cancelled
stale
```

Status should be extensible. Integrations may map external statuses into this base set.

## 9. Data model

### 9.1 Thread object

```json
{
  "thread_id": "thr_hackagent_qa_20260426_001",
  "type": "task",
  "status": "waiting_on_participant",
  "topic": "HackAgent QA account setup",
  "owner": "prd-bot",
  "participants": ["product-dev"],
  "created_by": {
    "type": "human",
    "id": "ian",
    "display_name": "Ian"
  },
  "source": {
    "platform": "telegram",
    "chat_id": "409747388",
    "message_id": "optional",
    "session_id": "optional"
  },
  "latest_summary": "Dev Agent has received the request and is creating six QA accounts.",
  "next_action": {
    "actor": "product-dev",
    "description": "Create QA accounts and update the linked Multica issue.",
    "due_at": null
  },
  "artifacts": [
    {
      "type": "multica_issue",
      "id": "OPE-105",
      "url": "optional"
    },
    {
      "type": "transcript",
      "path": "~/.hermes/a2a-transcripts/a2a-ope105-qa-accounts-20260425.jsonl"
    }
  ],
  "tags": ["hackagent", "qa"],
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:05:00Z",
  "closed_at": null,
  "metadata": {}
}
```

### 9.2 Event object

```json
{
  "event_id": "evt_01",
  "thread_id": "thr_hackagent_qa_20260426_001",
  "type": "message_sent",
  "actor": "prd-bot",
  "target": "product-dev",
  "summary": "Asked Dev Agent to create QA accounts.",
  "content": "Please create six QA accounts for HackAgent testing...",
  "transport": {
    "kind": "a2a_gateway",
    "target": "http://127.0.0.1:8643/v1/chat/completions",
    "session_id": "a2a-ope105-qa-accounts-20260425"
  },
  "artifact_refs": [],
  "created_at": "2026-04-26T10:02:00Z",
  "metadata": {}
}
```

### 9.3 Inbox item

Each agent can have an inbox. Inbox items are notifications derived from thread events.

```json
{
  "inbox_id": "inb_01",
  "agent": "product-dev",
  "thread_id": "thr_hackagent_qa_20260426_001",
  "kind": "assignment",
  "summary": "Product Agent assigned HackAgent QA account setup to you.",
  "read": false,
  "created_at": "2026-04-26T10:02:00Z"
}
```

## 10. Core workflows

### 10.1 Task delegation

```text
1. User asks Owner Agent to get another agent to handle something.
2. Owner Agent creates Thread(type=task, owner=Owner, participant=Assignee).
3. AgentThread links external task artifact if applicable, e.g. Multica issue.
4. Owner Agent notifies Assignee through configured transport.
5. Assignee updates Thread or linked task artifact.
6. User later asks Owner Agent "progress?".
7. Owner Agent queries recent owned threads and answers using latest_summary/status/artifacts.
```

### 10.2 Consultation

```text
1. User asks Owner Agent to ask another agent for opinion.
2. Owner Agent creates Thread(type=consultation).
3. Owner Agent sends consultation message through A2A/API/webhook.
4. Response is appended as event.
5. Thread latest_summary is updated.
6. User asks "what did they say?".
7. Owner Agent queries Thread and answers.
```

### 10.3 Reverse direction

Same mechanism works in reverse.

```text
Dev Agent receives request from Ian.
Dev Agent asks Product Agent.
owner = product-dev
participant = prd-bot
Ian later asks Dev Agent for progress.
Dev Agent queries owned thread.
```

### 10.4 Cross-session recovery

When an agent receives vague follow-up text:

```text
"progress?"
"what did dev say?"
"how's A going?"
"产品那边回复了吗？"
```

It should query:

1. recent threads owned by this agent in the same source session;
2. recent threads owned by this agent involving named participant;
3. recent threads matching topic keywords;
4. open/waiting threads before closed threads.

## 11. Transport adapters

Transport adapters deliver notifications or messages but do not own state.

Minimum adapter interface:

```python
class TransportAdapter:
    name: str

    def send(self, target: str, message: str, thread_id: str, metadata: dict) -> dict:
        """Deliver message and return delivery metadata."""
```

Recommended adapters:

### 11.1 Webhook adapter

POST signed JSON to an agent webhook endpoint.

Good for:

- Telegram environments without userbot;
- system-to-agent notification;
- local daemon wake-up.

### 11.2 A2A adapter

Use A2A JSON-RPC or Hermes gateway API to ask another agent for a response.

Good for:

- real-time consultation;
- request/response coordination;
- transcript capture.

### 11.3 File inbox adapter

Append JSONL to a target agent's inbox file.

Good for:

- local-first MVP;
- debugging;
- offline delivery;
- durable sync.

### 11.4 IM mirror adapter

Send human-visible mirror messages to Telegram, Slack, Discord, etc.

Good for:

- observability;
- group transparency;
- human audit trail.

Not good as source of truth.

## 12. API draft

### 12.1 CLI

```bash
agent-thread create \
  --type task \
  --owner prd-bot \
  --participant product-dev \
  --created-by ian \
  --source-platform telegram \
  --source-chat 409747388 \
  --topic "HackAgent QA accounts" \
  --summary "Ian asked Product Agent to get Dev Agent to create QA accounts"
```

```bash
agent-thread event append thr_xxx \
  --type message_sent \
  --actor prd-bot \
  --target product-dev \
  --summary "Asked Dev Agent to create QA accounts"
```

```bash
agent-thread update thr_xxx \
  --status waiting_on_participant \
  --next-actor product-dev \
  --next-action "Create accounts and update issue" \
  --summary "Dev Agent is working on QA account setup"
```

```bash
agent-thread recent \
  --owner prd-bot \
  --source-platform telegram \
  --source-chat 409747388 \
  --status open,waiting_on_participant,in_progress
```

```bash
agent-thread answer-context \
  --owner prd-bot \
  --query "进展怎么样" \
  --source-platform telegram \
  --source-chat 409747388
```

### 12.2 HTTP API

#### Create thread

```http
POST /threads
Content-Type: application/json
```

```json
{
  "type": "task",
  "owner": "prd-bot",
  "participants": ["product-dev"],
  "created_by": {"type": "human", "id": "ian"},
  "source": {"platform": "telegram", "chat_id": "409747388"},
  "topic": "HackAgent QA accounts",
  "latest_summary": "Ian asked Product Agent to get Dev Agent to create QA accounts."
}
```

#### Get thread

```http
GET /threads/{thread_id}
```

#### Append event

```http
POST /threads/{thread_id}/events
```

#### Update thread

```http
PATCH /threads/{thread_id}
```

#### Recent threads

```http
GET /threads/recent?owner=prd-bot&source_platform=telegram&source_chat=409747388&status=open,in_progress,waiting_on_participant
```

#### Inbox

```http
GET /agents/{agent_id}/inbox
POST /agents/{agent_id}/inbox
PATCH /agents/{agent_id}/inbox/{inbox_id}
```

## 13. Storage

### 13.1 MVP storage: SQLite

Recommended tables:

```sql
CREATE TABLE threads (
  thread_id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  topic TEXT NOT NULL,
  owner TEXT NOT NULL,
  participants_json TEXT NOT NULL,
  created_by_json TEXT NOT NULL,
  source_json TEXT,
  latest_summary TEXT,
  next_action_json TEXT,
  artifacts_json TEXT,
  tags_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  closed_at TEXT,
  metadata_json TEXT
);

CREATE INDEX idx_threads_owner_updated ON threads(owner, updated_at DESC);
CREATE INDEX idx_threads_owner_status ON threads(owner, status);
CREATE INDEX idx_threads_source ON threads(json_extract(source_json, '$.platform'), json_extract(source_json, '$.chat_id'));

CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  type TEXT NOT NULL,
  actor TEXT,
  target TEXT,
  summary TEXT,
  content TEXT,
  transport_json TEXT,
  artifact_refs_json TEXT,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
);

CREATE INDEX idx_events_thread_time ON events(thread_id, created_at);

CREATE TABLE inbox (
  inbox_id TEXT PRIMARY KEY,
  agent TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  summary TEXT,
  read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
);

CREATE INDEX idx_inbox_agent_read_time ON inbox(agent, read, created_at DESC);
```

### 13.2 Optional file mirror

For debugging and local inspection:

```text
~/.agent-thread/
  agentthread.db
  threads/
    thr_xxx.json
  events/
    thr_xxx.jsonl
  inbox/
    prd-bot.jsonl
    product-dev.jsonl
```

SQLite is canonical. JSON files are optional mirrors.

### 13.3 Storage philosophy: state vs memory

AgentThread separates canonical state from semantic memory.

Canonical state requires:

- deterministic lookup by `thread_id`;
- update-by-id;
- status filtering;
- ordering by `updated_at`;
- append-only event log;
- optional transactions;
- predictable owner/source/participant queries.

Semantic memory is optional and should be used for:

- fuzzy recall;
- completed-thread summaries;
- cross-thread insights;
- long-term project facts;
- natural-language search over historical work.

Therefore SQLite is the recommended default backend for active thread state. Project memory, vector memory, or runtime memory can be added as auxiliary recall backends. They should only be used as canonical storage if they support structured records, stable primary keys, update-by-id, deterministic filters, and append-only event semantics.

Recommended split:

```text
SQLite = source of truth for active thread state, status, events, inbox
Memory = semantic recall, completed-thread summaries, long-term insights
```

This avoids stale memory conflicts such as one memory saying `waiting_on_participant` while a newer state says `done`.

## 14. Recall algorithm

When an owner agent receives a follow-up query:

Input:

```json
{
  "owner": "prd-bot",
  "query": "进展怎么样",
  "source": {"platform": "telegram", "chat_id": "409747388"},
  "participants_hint": ["product-dev"],
  "topic_hint": "HackAgent"
}
```

Suggested ranking:

1. Same owner + same source session + open/waiting/in_progress.
2. Same owner + mentioned participant + open/waiting/in_progress.
3. Same owner + keyword match in topic/latest_summary/events.
4. Same owner + most recently updated open thread.
5. Closed threads only if query asks history.

Return compact context:

```json
{
  "thread_id": "thr_xxx",
  "topic": "HackAgent QA accounts",
  "status": "waiting_on_participant",
  "latest_summary": "Dev Agent is creating QA accounts.",
  "next_action": {"actor": "product-dev", "description": "Update OPE-105 when done"},
  "artifacts": [{"type": "multica_issue", "id": "OPE-105"}],
  "confidence": 0.91
}
```

## 15. Agent policy contract

Adapters can expose a simple policy prompt to participating agents:

```text
When you receive a user request that requires another agent:
1. Determine whether it is task, consultation, handoff, or notification.
2. Create or update an AgentThread.
3. Set yourself as owner unless explicitly handing off ownership.
4. Notify participants through configured transport.
5. Append all replies and status changes to the thread.
6. When the user asks for progress, query AgentThread before answering.
```

For task-like requests:

```text
If the request includes "handle", "fix", "follow up", "create", "deliver", "progress", or equivalent, prefer linking to a task artifact such as Multica/Linear/GitHub Issue.
```

For consultation-like requests:

```text
If the request is advice/review/brainstorm, no external task artifact is required, but the response must be summarized into the thread.
```

## 16. Hermes-specific integration draft

### 16.1 Current local agents

Example mapping:

```yaml
agents:
  prd-bot:
    display_name: 产品侠
    gateway: http://127.0.0.1:8642
    role: product
  product-dev:
    display_name: 研发侠
    gateway: http://127.0.0.1:8643
    role: engineering
  media:
    display_name: 媒体侠
    gateway: http://127.0.0.1:8644
    role: media
```

### 16.2 Recommended Hermes flow

Task:

```text
Product Agent receives request from Ian.
→ Create Multica issue.
→ Create AgentThread linked to issue.
→ Ask Dev Agent through A2A/gateway if immediate clarification is needed.
→ Dev Agent updates issue/thread.
→ Product Agent answers Ian by querying AgentThread + Multica.
```

Consultation:

```text
Owner Agent creates AgentThread(type=consultation).
→ Calls peer agent through existing a2a_send.py.
→ Appends peer reply to AgentThread.
→ Updates latest_summary.
→ Mirrors to Telegram group if configured.
```

Webhook sync:

```text
If target agent needs to be woken up but Telegram bot-to-bot is unavailable:
→ POST a signed webhook to target agent.
→ Webhook prompt tells target to update AgentThread or linked artifact.
```

### 16.3 Why this handles Telegram limitations

Telegram Bot API cannot be relied on for bot-to-bot messages or group mentions. AgentThread avoids depending on Telegram for inter-agent state.

Telegram can still be used as:

- human entry point;
- mirror/observability channel;
- final user delivery channel.

It should not be the source of truth for agent-to-agent collaboration.

## 17. Security and privacy

### 17.1 Sensitive data

Thread events may contain secrets, private user data, or internal context. Implementations should support:

- redaction before transport;
- configurable maximum event content size;
- secret pattern filtering;
- per-agent access control;
- audit log of reads/writes.

### 17.2 Access control

Minimum access model:

- owner can read/write thread;
- participants can read thread and append events;
- admin can read/write all;
- unrelated agents cannot read by default.

### 17.3 Transport trust

Transport responses are untrusted unless explicitly configured.

Every inbound external message should be labeled with source and transport metadata.

### 17.4 Prompt injection

AgentThread should distinguish:

- durable state fields (`status`, `latest_summary`, `next_action`);
- untrusted event content (`content`).

Agents should treat raw event content as untrusted transcript, not instructions.

## 18. MVP scope

### MVP 0: Local library + CLI

Build:

- SQLite storage;
- create/update/get/recent commands;
- append event;
- simple inbox;
- JSON output;
- basic keyword recall.

No server. No external transports required.

### MVP 1: Hermes adapter

Build:

- helper script usable from Hermes skills;
- wrap current `a2a_send.py` to update AgentThread;
- optional Multica artifact linking;
- Telegram mirror remains existing behavior.

### MVP 2: HTTP server

Build:

- FastAPI or stdlib HTTP server;
- REST endpoints for threads/events/inbox;
- token auth;
- OpenAPI spec.

### MVP 3: Transport adapters

Build:

- webhook adapter;
- A2A/Hermes gateway adapter;
- file inbox adapter;
- IM mirror adapter.

## 19. Acceptance criteria for MVP 0

1. Create a thread from CLI.
2. Append message/status events.
3. Update latest summary and next action.
4. Query recent open threads by owner.
5. Query recent threads by owner + source chat.
6. Get answer context for vague follow-up.
7. Inspect all data in SQLite and optional JSON export.
8. No network dependency.

## 20. Example end-to-end scenarios

### Scenario A: Product asks Dev

```text
Ian → Product Agent:
"Ask Dev Agent to create HackAgent QA accounts."

Product Agent:
- creates thread owner=prd-bot, participant=product-dev, type=task;
- creates Multica issue OPE-105;
- links OPE-105 as artifact;
- sends request to Dev Agent;
- updates thread latest_summary.

Dev Agent:
- creates accounts;
- updates OPE-105;
- appends done event.

Ian → Product Agent:
"进展怎么样？"

Product Agent:
- queries recent owner=prd-bot threads;
- finds HackAgent QA thread;
- answers with issue status and latest summary.
```

### Scenario B: Dev asks Product

```text
Ian → Dev Agent:
"Ask Product Agent whether this should be P0."

Dev Agent:
- creates thread owner=product-dev, participant=prd-bot, type=consultation;
- asks Product Agent;
- stores Product Agent's response.

Ian → Dev Agent:
"产品怎么说？"

Dev Agent:
- queries recent owner=product-dev threads;
- answers from latest_summary and transcript artifact.
```

### Scenario C: Media asks Product

```text
Media Agent needs product positioning for announcement.
owner=media
participant=prd-bot
type=consultation
status=answered
```

Same mechanics.

## 21. Open questions

1. Should task artifacts like Multica be mandatory for `type=task`, or optional but recommended?
2. Should ownership transfer be an event or a first-class status transition?
3. Should thread IDs be human-readable slugs, random IDs, or both?
4. How much raw transcript should be stored in events vs artifact references?
5. Should recall use SQLite FTS5 in MVP 0?
6. Should access control be enforced in local CLI mode or only server mode?
7. What is the default retention policy?
8. How should agent identity be authenticated across adapters?

## 22. Initial implementation plan

### Phase 1: Local core

Files:

```text
agentthread/
  __init__.py
  models.py
  store.py
  cli.py
  recall.py
  ids.py
tests/
  test_store.py
  test_cli.py
  test_recall.py
```

Tasks:

1. Define Pydantic/dataclass models for Thread, Event, InboxItem.
2. Implement SQLite schema and migrations.
3. Implement create/get/update thread.
4. Implement append event.
5. Implement inbox create/list/mark-read.
6. Implement recent query.
7. Implement simple recall ranking.
8. Implement CLI.
9. Add JSON export.
10. Write README quickstart.

### Phase 2: Hermes integration

Files:

```text
integrations/hermes/
  a2a_state_wrapper.py
  skill/AgentThread/SKILL.md
```

Tasks:

1. Add helper to create/update threads around existing `a2a_send.py`.
2. Add support for owner/participant mapping.
3. Add optional Multica artifact link.
4. Add recall helper for vague progress questions.
5. Dogfood with prd-bot/product-dev/media.

### Phase 3: Server + adapters

Files:

```text
agentthread/server.py
agentthread/adapters/webhook.py
agentthread/adapters/hermes_gateway.py
agentthread/adapters/file_inbox.py
```

Tasks:

1. FastAPI server.
2. Token auth.
3. REST endpoints.
4. Webhook adapter.
5. Hermes gateway adapter.
6. Dockerfile.
7. OpenAPI docs.

## 23. README pitch draft

```markdown
# AgentThread

Persistent collaboration threads for multi-agent systems.

Agents can already talk. The hard part is remembering who owns the work, what another agent replied, and what to say when the user asks "progress?" later.

AgentThread provides a lightweight state layer for cross-agent delegation, consultation, handoff, and progress recall across Telegram, Slack, Discord, webhooks, CLI, and custom agent runtimes.
```

## 24. License recommendation

MIT or Apache-2.0.

MIT is simpler and better for adoption. Apache-2.0 is better if patent protection matters.

## 25. Current recommendation

Start with `AgentThread` as a local-first CLI/library, not a server and not a protocol replacement.

Use it internally for:

```text
产品侠 ↔ 研发侠 ↔ 媒体侠
```

Once it reliably solves owner recall and progress follow-up, package it as an open-source project with Hermes as the first integration.
