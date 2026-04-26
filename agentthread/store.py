"""SQLite canonical storage for AgentThread MVP0."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .ids import new_id, utc_now
from .models import Event, InboxItem, Thread


DEFAULT_DB_PATH = Path("~/.agent-thread/agentthread.db").expanduser()
ACTIVE_STATUSES = {"open", "waiting_on_owner", "waiting_on_participant", "in_progress", "blocked"}


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_load(value: str | None, default: Any) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


def _sqlite_integrity_error(message: str, exc: sqlite3.IntegrityError) -> ValueError:
    return ValueError(message).with_traceback(exc.__traceback__)


class Store:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path).expanduser() if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS threads (
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
                CREATE INDEX IF NOT EXISTS idx_threads_owner_updated ON threads(owner, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_threads_owner_status ON threads(owner, status);
                CREATE INDEX IF NOT EXISTS idx_threads_source ON threads(
                  json_extract(source_json, '$.platform'),
                  json_extract(source_json, '$.chat_id')
                );

                CREATE TABLE IF NOT EXISTS events (
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
                CREATE INDEX IF NOT EXISTS idx_events_thread_time ON events(thread_id, created_at);

                CREATE TABLE IF NOT EXISTS inbox (
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
                CREATE INDEX IF NOT EXISTS idx_inbox_agent_read_time ON inbox(agent, read, created_at DESC);
                """
            )

    def create_thread(
        self,
        *,
        type: str,
        owner: str,
        topic: str,
        participants: list[str] | None = None,
        status: str = "open",
        created_by: dict[str, Any] | None = None,
        source: dict[str, Any] | None = None,
        latest_summary: str | None = None,
        next_action: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        thread = Thread(
            thread_id=thread_id or new_id("thr"),
            type=type,
            status=status,
            topic=topic,
            owner=owner,
            participants=participants or [],
            created_by=created_by or {},
            source=source,
            latest_summary=latest_summary,
            next_action=next_action,
            artifacts=artifacts or [],
            tags=tags or [],
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO threads (
                      thread_id, type, status, topic, owner, participants_json,
                      created_by_json, source_json, latest_summary, next_action_json,
                      artifacts_json, tags_json, created_at, updated_at, closed_at,
                      metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._thread_values(thread),
                )
        except sqlite3.IntegrityError as exc:
            if "threads.thread_id" in str(exc):
                raise _sqlite_integrity_error(f"Duplicate thread_id: {thread.thread_id}", exc) from None
            raise
        return thread.to_dict()

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,)).fetchone()
        return self._row_to_thread(row) if row else None

    def update_thread(self, thread_id: str, **updates: Any) -> dict[str, Any] | None:
        allowed = {
            "type": "type",
            "status": "status",
            "topic": "topic",
            "owner": "owner",
            "participants": "participants_json",
            "created_by": "created_by_json",
            "source": "source_json",
            "latest_summary": "latest_summary",
            "next_action": "next_action_json",
            "artifacts": "artifacts_json",
            "tags": "tags_json",
            "closed_at": "closed_at",
            "metadata": "metadata_json",
        }
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key not in allowed:
                raise ValueError(f"Unsupported thread field: {key}")
            column = allowed[key]
            if column.endswith("_json"):
                value = _json_dump(value)
            assignments.append(f"{column} = ?")
            values.append(value)
        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(thread_id)
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE threads SET {', '.join(assignments)} WHERE thread_id = ?", values)
            if cur.rowcount == 0:
                return None
        return self.get_thread(thread_id)

    def append_event(
        self,
        thread_id: str,
        *,
        type: str,
        actor: str | None = None,
        target: str | None = None,
        summary: str | None = None,
        content: str | None = None,
        transport: dict[str, Any] | None = None,
        artifact_refs: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        if self.get_thread(thread_id) is None:
            raise KeyError(f"Unknown thread_id: {thread_id}")
        event = Event(
            event_id=event_id or new_id("evt"),
            thread_id=thread_id,
            type=type,
            actor=actor,
            target=target,
            summary=summary,
            content=content,
            transport=transport,
            artifact_refs=artifact_refs or [],
            created_at=utc_now(),
            metadata=metadata or {},
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                  event_id, thread_id, type, actor, target, summary, content,
                  transport_json, artifact_refs_json, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.thread_id,
                    event.type,
                    event.actor,
                    event.target,
                    event.summary,
                    event.content,
                    _json_dump(event.transport) if event.transport is not None else None,
                    _json_dump(event.artifact_refs),
                    event.created_at,
                    _json_dump(event.metadata),
                ),
            )
            conn.execute("UPDATE threads SET updated_at = ? WHERE thread_id = ?", (event.created_at, thread_id))
        return event.to_dict()

    def list_events(self, thread_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events WHERE thread_id = ? ORDER BY created_at ASC"
        params: list[Any] = [thread_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def export_thread(self, thread_id: str) -> dict[str, Any]:
        thread = self.get_thread(thread_id)
        if thread is None:
            raise KeyError(f"Unknown thread_id: {thread_id}")
        return {"thread": thread, "events": self.list_events(thread_id)}

    def create_inbox_item(
        self,
        *,
        agent: str,
        thread_id: str,
        kind: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
        inbox_id: str | None = None,
    ) -> dict[str, Any]:
        if self.get_thread(thread_id) is None:
            raise KeyError(f"Unknown thread_id: {thread_id}")
        item = InboxItem(
            inbox_id=inbox_id or new_id("inb"),
            agent=agent,
            thread_id=thread_id,
            kind=kind,
            summary=summary,
            created_at=utc_now(),
            metadata=metadata or {},
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inbox (inbox_id, agent, thread_id, kind, summary, read, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.inbox_id,
                    item.agent,
                    item.thread_id,
                    item.kind,
                    item.summary,
                    int(item.read),
                    item.created_at,
                    _json_dump(item.metadata),
                ),
            )
        return item.to_dict()

    def list_inbox(self, agent: str, unread_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        sql = "SELECT * FROM inbox WHERE agent = ?"
        params: list[Any] = [agent]
        if unread_only:
            sql += " AND read = 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_inbox(row) for row in rows]

    def mark_inbox_read(self, inbox_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            cur = conn.execute("UPDATE inbox SET read = 1 WHERE inbox_id = ?", (inbox_id,))
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM inbox WHERE inbox_id = ?", (inbox_id,)).fetchone()
        return self._row_to_inbox(row) if row else None

    def recent_threads(
        self,
        *,
        owner: str,
        source: dict[str, Any] | None = None,
        statuses: Iterable[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        where = ["owner = ?"]
        params: list[Any] = [owner]
        status_list = list(statuses or [])
        if status_list:
            where.append(f"status IN ({','.join('?' for _ in status_list)})")
            params.extend(status_list)
        if source:
            if source.get("platform") is not None:
                where.append("json_extract(source_json, '$.platform') = ?")
                params.append(source["platform"])
            if source.get("chat_id") is not None:
                where.append("json_extract(source_json, '$.chat_id') = ?")
                params.append(str(source["chat_id"]))
        params.append(limit)
        active_order = ",".join(f"'{status}'" for status in sorted(ACTIVE_STATUSES))
        sql = (
            f"SELECT * FROM threads WHERE {' AND '.join(where)} "
            f"ORDER BY CASE WHEN status IN ({active_order}) THEN 0 ELSE 1 END, updated_at DESC LIMIT ?"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_thread(row) for row in rows]

    def _thread_values(self, thread: Thread) -> tuple[Any, ...]:
        return (
            thread.thread_id,
            thread.type,
            thread.status,
            thread.topic,
            thread.owner,
            _json_dump(thread.participants),
            _json_dump(thread.created_by),
            _json_dump(thread.source) if thread.source is not None else None,
            thread.latest_summary,
            _json_dump(thread.next_action) if thread.next_action is not None else None,
            _json_dump(thread.artifacts),
            _json_dump(thread.tags),
            thread.created_at,
            thread.updated_at,
            thread.closed_at,
            _json_dump(thread.metadata),
        )

    def _row_to_thread(self, row: sqlite3.Row) -> dict[str, Any]:
        return Thread(
            thread_id=row["thread_id"],
            type=row["type"],
            status=row["status"],
            topic=row["topic"],
            owner=row["owner"],
            participants=_json_load(row["participants_json"], []),
            created_by=_json_load(row["created_by_json"], {}),
            source=_json_load(row["source_json"], None),
            latest_summary=row["latest_summary"],
            next_action=_json_load(row["next_action_json"], None),
            artifacts=_json_load(row["artifacts_json"], []),
            tags=_json_load(row["tags_json"], []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
            metadata=_json_load(row["metadata_json"], {}),
        ).to_dict()

    def _row_to_event(self, row: sqlite3.Row) -> dict[str, Any]:
        return Event(
            event_id=row["event_id"],
            thread_id=row["thread_id"],
            type=row["type"],
            actor=row["actor"],
            target=row["target"],
            summary=row["summary"],
            content=row["content"],
            transport=_json_load(row["transport_json"], None),
            artifact_refs=_json_load(row["artifact_refs_json"], []),
            created_at=row["created_at"],
            metadata=_json_load(row["metadata_json"], {}),
        ).to_dict()

    def _row_to_inbox(self, row: sqlite3.Row) -> dict[str, Any]:
        return InboxItem(
            inbox_id=row["inbox_id"],
            agent=row["agent"],
            thread_id=row["thread_id"],
            kind=row["kind"],
            summary=row["summary"],
            read=bool(row["read"]),
            created_at=row["created_at"],
            metadata=_json_load(row["metadata_json"], {}),
        ).to_dict()
