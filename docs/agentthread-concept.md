# AgentThread Concept Document

## Summary

AgentThread is a lightweight collaboration state layer for multi-agent systems.

Agents can already talk through A2A, gateway APIs, webhooks, IM bots, or task systems. The harder problem is making sure the right agent remembers:

- who owns the work;
- who was asked to help;
- what the other agent replied;
- what the latest status is;
- what the next action is;
- how to answer when the user later asks, "progress?".

AgentThread solves this by introducing persistent collaboration threads that sit above transport layers and below product-specific task workflows.

## The problem

In real deployments, agents are not just functions inside a single orchestrator. They often run as independent daemons connected to different surfaces:

- Telegram bots;
- Slack apps;
- Discord bots;
- webhook workers;
- API server sessions;
- cron jobs;
- CLI sessions;
- internal task runners.

Each surface may create a different session and memory context. This makes agent-to-agent coordination fragile.

Typical failure:

```text
Ian talks to Product Agent about A.
Ian asks Product Agent to get Dev Agent to handle it.
Product Agent talks to Dev Agent through A2A/API/group mirror.
Ian later asks Product Agent: "How is it going?"
Product Agent does not know which thread, what Dev Agent replied, or current status.
```

This is not primarily a transport failure. The message may have been sent successfully. It is a state ownership failure.

## Core insight

Cross-agent work needs a durable object, not just messages.

That object is a **Thread**.

A Thread records:

```text
user request → owner agent → participant agents → messages/events → latest status → next action → artifacts
```

The owner is the agent responsible for answering future user follow-ups.

Direction does not matter:

```text
Product Agent asks Dev Agent → owner = Product Agent
Dev Agent asks Product Agent → owner = Dev Agent
Media Agent asks Product Agent → owner = Media Agent
```

## What AgentThread is

AgentThread is:

- a thread registry;
- an append-only event log;
- a lightweight inbox per agent;
- a recall layer for vague follow-up questions;
- a bridge between A2A/IM/webhooks and task systems like Multica, Linear, or GitHub Issues.

## What AgentThread is not

AgentThread is not:

- an A2A protocol replacement;
- a chatbot framework;
- an IM bot;
- a vector memory product;
- a task manager UI first;
- a central LLM orchestrator.

A2A lets agents talk. AgentThread lets agents remember who is responsible, what happened, and what comes next.

## Example: task delegation

```text
Ian → Product Agent:
"Ask Dev Agent to create HackAgent QA accounts."
```

Product Agent creates a Thread:

```json
{
  "type": "task",
  "owner": "prd-bot",
  "participants": ["product-dev"],
  "topic": "HackAgent QA account setup",
  "status": "waiting_on_participant",
  "latest_summary": "Dev Agent has been asked to create QA accounts.",
  "next_action": {
    "actor": "product-dev",
    "description": "Create accounts and update linked issue."
  }
}
```

Then Product Agent can:

- create/link a Multica issue;
- notify Dev Agent through A2A/webhook;
- append Dev Agent's response as an event;
- update latest status.

When Ian later asks Product Agent:

```text
进展怎么样？
```

Product Agent queries AgentThread and answers from the latest state.

## Example: consultation

```text
Ian → Dev Agent:
"Ask Product Agent whether this should be P0."
```

Dev Agent creates:

```json
{
  "type": "consultation",
  "owner": "product-dev",
  "participants": ["prd-bot"],
  "topic": "Priority of feature A",
  "status": "answered"
}
```

Product Agent's answer is stored in the thread. Later Ian asks Dev Agent:

```text
产品怎么说？
```

Dev Agent retrieves the thread and answers.

## Why this matters across IM platforms

Telegram bot-to-bot messages are unreliable or filtered. Other IM platforms have their own restrictions around app-to-app messaging, bot intents, permissions, and sessions.

AgentThread avoids depending on IM delivery for state.

IM platforms become:

- user entry points;
- notification surfaces;
- human-visible mirrors.

The Thread remains the source of truth.

## Storage philosophy

AgentThread separates canonical state from semantic memory.

Canonical state needs:

- deterministic lookup by `thread_id`;
- update-by-id;
- status filtering;
- ordering by `updated_at`;
- append-only events;
- optional transactions.

SQLite is the recommended MVP backend because it is local, embedded, dependency-light, deterministic, and good at exactly these queries.

Project memory or vector memory can be used as an auxiliary recall layer, especially for fuzzy search and completed-thread summaries. It should not replace canonical state unless it supports structured records, primary keys, update-by-id, deterministic filters, and reliable event append semantics.

Recommended split:

```text
SQLite = source of truth for active thread state
Memory = semantic recall and long-term summaries
```

## MVP shape

MVP should be local-first:

```text
~/.agent-thread/agentthread.db
```

Core tables:

- `threads`
- `events`
- `inbox`

Core CLI:

```bash
agent-thread create
agent-thread update
agent-thread event append
agent-thread recent
agent-thread answer-context
```

No server is needed for MVP 0.

## Open-source positioning

Suggested project name:

```text
AgentThread
```

Tagline:

```text
Persistent collaboration threads for multi-agent systems.
```

README pitch:

```text
Agents can already talk. The hard part is remembering who owns the work, what another agent replied, and what to say when the user asks "progress?" later.

AgentThread provides a lightweight state layer for cross-agent delegation, consultation, handoff, and progress recall across Telegram, Slack, Discord, webhooks, CLI, and custom agent runtimes.
```
