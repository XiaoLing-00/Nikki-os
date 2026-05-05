from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


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
    ) -> None:
        if not key_info:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO memories(key_info, sentiment, source, created_at) VALUES(?, ?, ?, ?)",
                    (key_info.strip(), sentiment, source, now),
                )
                conn.execute(
                    """
                    INSERT INTO interaction_history(summary, sentiment, source, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (key_info.strip(), sentiment, source, now),
                )
                self._increment_stat(conn, "affection", 2 if sentiment == "positive" else 1)

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
