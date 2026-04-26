# Hermes AgentThread Rollout

This rollout is for Ian's Hermes multi-agent setup (`产品侠`, `研发侠`, `媒体侠`).

## Decision

Do **not** turn AgentThread on as a new handoff mechanism before cleaning the old A2A instructions.

The current reliable split is:

| Intent | Channel | AgentThread role |
|---|---|---|
| Project work / QA / bugfix / implementation | `multica issue create` | Record canonical thread state and artifacts around the Multica issue |
| Real-time consultation / brainstorm / architecture check | `a2a-chat` transport | Wrap the A2A call with `send_threaded_a2a()` so the owner can later answer "progress?" |
| Notify Ian / humans | `send_message` | Optional event artifact only; never use it to wake agents |

AgentThread is a state layer, not a wake-up transport. It should not reintroduce HTTP gateway calls or Telegram bot mentions as task triggers.

## Cleanup required before pilot

Remove or rewrite stale instructions in bot profiles that say or imply:

- `curl http://127.0.0.1:<port>/v1/chat/completions` is a task handoff path.
- `send_message(target="telegram:-1003776690352", message="@<bot> ...")` can wake another agent.
- Existing issue `comment`, `status`, or `reassign` reliably wakes another agent.
- A2A chat is a fallback when Multica task dispatch fails.

The replacement wording should be:

- Work handoff: create a **new Multica issue** assigned to the target agent.
- Real-time consultation: use AgentThread-wrapped A2A only when the goal is discussion, not task execution.
- Human notification: use `send_message` only for Ian/human-readable progress updates.

## Pilot sequence

1. Install local package in the runtime environment:
   ```bash
   cd /home/bre/agentthread
   python -m pip install -e .
   agent-thread --help
   ```

2. Create a small smoke thread, not involving production agents:
   ```bash
   agent-thread create \
     --type consultation \
     --owner hermes-ian \
     --participant product-dev \
     --created-by ian \
     --source-platform telegram \
     --source-chat 409747388 \
     --topic "AgentThread smoke test" \
     --summary "Local smoke test for threaded collaboration state."
   ```

3. Enable product/dev profile docs to use this rule:
   - `multica issue create` for all real work;
   - `send_threaded_a2a()` only for consultative A2A chat;
   - `agent-thread answer-context` before answering vague follow-ups like “进展呢？”.

4. Run one controlled consultation from 产品侠 to 研发侠 using `send_threaded_a2a()` with a harmless question.

5. Verify:
   ```bash
   agent-thread recent --owner prd-bot --limit 5
   agent-thread answer-context --owner prd-bot --query "进展呢？" --source-platform telegram --source-chat 409747388
   ```

6. Only after the above is stable, add a small profile skill named `agentthread-collaboration-state` to 产品侠/研发侠.

## Rollback

AgentThread is local-first and non-invasive. Rollback is simply:

- Stop using the wrapper in profile instructions.
- Keep Multica as the source of task execution truth.
- The SQLite DB at `~/.agent-thread/agentthread.db` can be retained for audit or moved aside.
