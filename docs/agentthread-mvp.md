# AgentThread MVP0 Quickstart

AgentThread MVP0 is a local Python package and JSON CLI backed by SQLite.
It stores canonical collaboration state in:

```text
~/.agent-thread/agentthread.db
```

Use `--db /path/to/agentthread.db` for tests or isolated local runs.

## Create a Thread

```bash
python -m agentthread.cli create \
  --type task \
  --owner prd-bot \
  --participant product-dev \
  --created-by ian \
  --source-platform telegram \
  --source-chat 409747388 \
  --topic "HackAgent QA accounts" \
  --summary "Ian asked Product Agent to get Dev Agent to create QA accounts."
```

## Update Status

```bash
python -m agentthread.cli update thr_xxx \
  --status waiting_on_participant \
  --next-actor product-dev \
  --next-action "Create accounts and update issue" \
  --summary "Dev Agent is creating QA accounts."
```

## Append an Event

```bash
python -m agentthread.cli event append thr_xxx \
  --type message_sent \
  --actor prd-bot \
  --target product-dev \
  --summary "Asked Dev Agent to create QA accounts."
```

## Recent Threads

```bash
python -m agentthread.cli recent \
  --owner prd-bot \
  --source-platform telegram \
  --source-chat 409747388
```

## Answer Context

```bash
python -m agentthread.cli answer-context \
  --owner prd-bot \
  --query "进展怎么样" \
  --source-platform telegram \
  --source-chat 409747388
```

All commands print JSON. MVP0 has no server, no network dependency, and uses only the Python standard library at runtime.
