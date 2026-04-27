# AgentThread

Persistent collaboration threads for multi-agent systems.

Agents can already talk through A2A, gateway APIs, webhooks, IM bots, or task systems. The hard part is remembering who owns the work, what another agent replied, what the latest status is, and what to say when the user later asks "progress?"

AgentThread is a small local-first state layer for delegation, consultation, handoff, and progress recall. MVP0 is a Python package and JSON CLI backed by SQLite. Runtime code uses only the Python standard library.

## Install

For local development:

```bash
python -m pip install -e .
```

For one-off use without installing:

```bash
python -m agentthread.cli --help
```

AgentThread stores its default database at:

```text
~/.agent-thread/agentthread.db
```

Use `--db /path/to/agentthread.db` for tests, experiments, or isolated agent runtimes.

## Development

```bash
python -m pytest
```

The project has no runtime dependencies beyond Python and SQLite from the standard library. Test tooling is intentionally outside the package runtime contract.

## Quickstart

For stable agent collaboration, use the high-level workflow CLI first:

- `agentthread task create` — work delegation; must use a task backend.
- `agentthread ask` — consultation/review; always records an AgentThread.
- `agentthread notify` — human notification; rejects agent targets.
- `agentthread audit` — flags raw A2A transcripts without AgentThread state.
- `agentthread doctor` — checks local readiness.
- `agentthread policy` — prints active workflow guardrails.

The lower-level `agent-thread` CLI remains available for direct state inspection and repair.

Create a thread when one agent owns a user request and another participant needs to help:

```bash
agent-thread create \
  --type task \
  --owner prd-bot \
  --participant product-dev \
  --created-by ian \
  --source-platform telegram \
  --source-chat 409747388 \
  --topic "HackAgent QA accounts" \
  --summary "Ian asked Product Agent to get Dev Agent to create QA accounts."
```

Update the current state:

```bash
agent-thread update thr_xxx \
  --status waiting_on_participant \
  --next-actor product-dev \
  --next-action "Create accounts and update issue" \
  --summary "Dev Agent is creating QA accounts."
```

Append an event:

```bash
agent-thread event append thr_xxx \
  --type message_sent \
  --actor prd-bot \
  --target product-dev \
  --summary "Asked Dev Agent to create QA accounts."
```

Recall likely context when a user asks a vague follow-up:

```bash
agent-thread answer-context \
  --owner prd-bot \
  --query "progress?" \
  --source-platform telegram \
  --source-chat 409747388
```

All commands print JSON.

## CLI Examples

Fetch a thread:

```bash
agent-thread get thr_xxx
```

List events:

```bash
agent-thread events thr_xxx
```

Export a full thread record with its event log:

```bash
agent-thread export thr_xxx
```

List recent owner threads:

```bash
agent-thread recent --owner prd-bot --limit 10
```

List and mark inbox items:

```bash
agent-thread inbox list --agent product-dev
agent-thread inbox read inb_xxx
```

Pass structured fields as JSON during creation:

```bash
agent-thread create \
  --type task \
  --owner prd-bot \
  --participant product-dev \
  --topic "Structured delegation" \
  --json '{"created_by":{"type":"human","id":"ian"},"source":{"platform":"telegram","chat_id":"409747388"},"next_action":{"actor":"product-dev","description":"Reply with status"},"artifacts":[{"type":"linear_issue","id":"AT-1"}],"tags":["agentthread"],"metadata":{"priority":1}}'
```

Update structured fields:

```bash
agent-thread update thr_xxx \
  --json '{"next_action":{"actor":"prd-bot","description":"Follow up"},"metadata":{"priority":2}}'
```

## How It Relates

A2A and webhooks move messages between agents. AgentThread records ownership, status, events, next actions, and artifacts so the owner can answer later.

IM platforms such as Telegram, Slack, Discord, Feishu, and Matrix are entry points or notification surfaces. They are not the source of truth.

SQLite is the MVP source of truth because it gives deterministic IDs, updates, filters, ordering, foreign keys, and append-only event history without running a server.

Memory systems are complementary. Use memory or vector recall for fuzzy long-term summaries; use AgentThread for canonical active collaboration state.
