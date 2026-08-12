from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from memory.memory_trigger import contains_sensitive_information


@dataclass
class LongMemory:
    database_path: Path

    def __post_init__(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_info TEXT NOT NULL,
                        sentiment TEXT DEFAULT 'neutral',
                        source TEXT DEFAULT 'dialogue',
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_sessions (
                        app_key TEXT PRIMARY KEY,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        active_seconds INTEGER DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_profile (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interaction_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        summary TEXT NOT NULL,
                        sentiment TEXT DEFAULT 'neutral',
                        source TEXT DEFAULT 'dialogue',
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS character_stats (
                        key TEXT PRIMARY KEY,
                        value INTEGER NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    """
                    INSERT OR IGNORE INTO user_profile(key, value, updated_at)
                    VALUES('name', '晓灵', ?)
                    """,
                    (now,),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO character_stats(key, value, updated_at)
                    VALUES('affection', 0, ?)
                    """,
                    (now,),
                )

    def add_memory(
        self,
        key_info: str | None,
        sentiment: str = "neutral",
        source: str = "dialogue",
    ) -> bool:
        if not key_info or contains_sensitive_information(key_info):
            return False
        key_info = " ".join(key_info.strip().split())[:300]
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                duplicate = conn.execute(
                    "SELECT id FROM memories WHERE lower(key_info) = lower(?) LIMIT 1",
                    (key_info,),
                ).fetchone()
                if duplicate:
                    return False
                conn.execute(
                    "INSERT INTO memories(key_info, sentiment, source, created_at) VALUES(?, ?, ?, ?)",
                    (key_info, sentiment, source, now),
                )
                conn.execute(
                    """
                    INSERT INTO interaction_history(summary, sentiment, source, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (key_info, sentiment, source, now),
                )
                self._increment_stat(conn, "affection", 2 if sentiment == "positive" else 1)
        return True

    def list_memories(self, limit: int = 500) -> list[dict[str, str | int]]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, key_info, sentiment, source, created_at FROM memories ORDER BY id DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_memory(self, memory_id: int, key_info: str, sentiment: str = "neutral") -> bool:
        clean = " ".join(key_info.strip().split())[:300]
        if not clean or contains_sensitive_information(clean):
            return False
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"
        with closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    "UPDATE memories SET key_info = ?, sentiment = ? WHERE id = ?",
                    (clean, sentiment, memory_id),
                )
        return cursor.rowcount > 0

    def delete_memory(self, memory_id: int) -> bool:
        with closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    def clear_memories(self) -> int:
        with closing(self._connect()) as conn:
            with conn:
                count = int(conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
                conn.execute("DELETE FROM memories")
                conn.execute("DELETE FROM interaction_history")
        return count

    def recent_memories(self, limit: int = 8) -> list[dict[str, str]]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT key_info, sentiment, source, created_at
                FROM memories
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def relevant_memories(self, query: str, limit: int = 8) -> list[dict[str, str]]:
        candidates = self.list_memories(limit=200)
        terms = {
            term.lower()
            for term in re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", query)
        }
        if not terms:
            return [dict(item) for item in candidates[:limit]]

        def score(item: dict[str, str | int]) -> tuple[int, int]:
            text = str(item["key_info"]).lower()
            matches = sum(1 for term in terms if term in text)
            return matches, int(item["id"])

        ranked = sorted(candidates, key=score, reverse=True)
        relevant = [dict(item) for item in ranked if score(item)[0] > 0]
        return relevant[:limit] or [dict(item) for item in candidates[: min(3, limit)]]

    def prune_memories(self, max_count: int = 500) -> int:
        max_count = max(20, max_count)
        with closing(self._connect()) as conn:
            with conn:
                before = int(conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
                conn.execute(
                    "DELETE FROM memories WHERE id NOT IN (SELECT id FROM memories ORDER BY id DESC LIMIT ?)",
                    (max_count,),
                )
        return max(0, before - max_count)

    def profile(self) -> dict[str, str]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
        return {str(key): str(value) for key, value in rows}

    def stats(self) -> dict[str, int]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT key, value FROM character_stats").fetchall()
        return {str(key): int(value) for key, value in rows}

    def recent_interactions(self, limit: int = 5) -> list[dict[str, str]]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT summary, sentiment, source, created_at
                FROM interaction_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def touch_app(self, app_key: str, interval_seconds: int, reset_gap_minutes: int = 5) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                row = conn.execute(
                    "SELECT active_seconds, last_seen FROM app_sessions WHERE app_key = ?",
                    (app_key,),
                ).fetchone()
                if row is None:
                    active_seconds = interval_seconds
                    conn.execute(
                        """
                        INSERT INTO app_sessions(app_key, first_seen, last_seen, active_seconds)
                        VALUES(?, ?, ?, ?)
                        """,
                        (app_key, now, now, active_seconds),
                    )
                else:
                    last_seen = datetime.fromisoformat(row[1])
                    current_time = datetime.fromisoformat(now)
                    gap_seconds = (current_time - last_seen).total_seconds()
                    if gap_seconds > reset_gap_minutes * 60:
                        active_seconds = interval_seconds
                    else:
                        active_seconds = int(row[0]) + interval_seconds
                    conn.execute(
                        """
                        UPDATE app_sessions
                        SET last_seen = ?, active_seconds = ?
                        WHERE app_key = ?
                        """,
                        (now, active_seconds, app_key),
                    )
        return active_seconds

    @staticmethod
    def _increment_stat(conn: sqlite3.Connection, key: str, delta: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO character_stats(key, value, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = value + excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, delta, now),
        )
