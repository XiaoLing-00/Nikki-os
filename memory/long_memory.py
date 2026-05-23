from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
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
                    CREATE TABLE IF NOT EXISTS memory_candidates (
                        key_info TEXT PRIMARY KEY,
                        sentiment TEXT DEFAULT 'neutral',
                        source TEXT DEFAULT 'dialogue',
                        occurrences INTEGER NOT NULL DEFAULT 1,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL
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
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_progress (
                        title TEXT PRIMARY KEY,
                        project TEXT DEFAULT '',
                        chapter TEXT DEFAULT '',
                        subtask TEXT DEFAULT '',
                        priority TEXT DEFAULT 'normal',
                        status TEXT DEFAULT 'in_progress',
                        source TEXT DEFAULT 'dialogue',
                        last_touched TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_state (
                        day TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        source TEXT DEFAULT 'dialogue',
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(day, key)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS emotional_patterns (
                        label TEXT PRIMARY KEY,
                        weight REAL NOT NULL DEFAULT 1,
                        occurrences INTEGER NOT NULL DEFAULT 1,
                        last_seen TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    """
                    INSERT OR IGNORE INTO user_profile(key, value, updated_at)
                    VALUES('name', '00', ?)
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
        require_repetition: bool = False,
    ) -> None:
        if not key_info:
            return
        if require_repetition and not self._record_memory_candidate(key_info, sentiment, source):
            return
        self._insert_memory(key_info, sentiment, source)

    def _insert_memory(
        self,
        key_info: str,
        sentiment: str = "neutral",
        source: str = "dialogue",
    ) -> None:
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

    def _record_memory_candidate(self, key_info: str, sentiment: str, source: str) -> bool:
        normalized = " ".join(key_info.strip().split())
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                row = conn.execute(
                    "SELECT occurrences FROM memory_candidates WHERE key_info = ?",
                    (normalized,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO memory_candidates(key_info, sentiment, source, occurrences, first_seen, last_seen)
                        VALUES(?, ?, ?, 1, ?, ?)
                        """,
                        (normalized, sentiment, source, now, now),
                    )
                    return False
                occurrences = int(row[0]) + 1
                conn.execute(
                    """
                    UPDATE memory_candidates
                    SET sentiment = ?, source = ?, occurrences = ?, last_seen = ?
                    WHERE key_info = ?
                    """,
                    (sentiment, source, occurrences, now, normalized),
                )
                if occurrences < 3:
                    return False
                conn.execute("DELETE FROM memory_candidates WHERE key_info = ?", (normalized,))
        return True

    def upsert_task(
        self,
        title: str | None,
        project: str = "",
        chapter: str = "",
        subtask: str = "",
        priority: str = "normal",
        status: str = "in_progress",
        source: str = "dialogue",
    ) -> None:
        if not title or not title.strip():
            return
        priority = priority if priority in {"urgent", "high", "normal", "low"} else "normal"
        status = status if status in {"todo", "in_progress", "blocked", "done"} else "in_progress"
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO task_progress(title, project, chapter, subtask, priority, status, source, last_touched, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(title) DO UPDATE SET
                        project = COALESCE(NULLIF(excluded.project, ''), task_progress.project),
                        chapter = COALESCE(NULLIF(excluded.chapter, ''), task_progress.chapter),
                        subtask = COALESCE(NULLIF(excluded.subtask, ''), task_progress.subtask),
                        priority = excluded.priority,
                        status = excluded.status,
                        source = excluded.source,
                        last_touched = excluded.last_touched,
                        updated_at = excluded.updated_at
                    """,
                    (
                        title.strip(),
                        project.strip(),
                        chapter.strip(),
                        subtask.strip(),
                        priority,
                        status,
                        source,
                        now,
                        now,
                    ),
                )

    def active_tasks(self, limit: int = 5) -> list[dict[str, str]]:
        priority_sql = "CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END"
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT title, project, chapter, subtask, priority, status, source, last_touched, updated_at
                FROM task_progress
                WHERE status != 'done'
                ORDER BY {priority_sql}, datetime(last_touched) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def current_task(self) -> dict[str, str] | None:
        tasks = self.active_tasks(limit=1)
        return tasks[0] if tasks else None

    def add_daily_state(self, key: str | None, value: str | None, source: str = "dialogue") -> None:
        if not key or not value:
            return
        now = datetime.now().isoformat(timespec="seconds")
        today = date.today().isoformat()
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO daily_state(day, key, value, source, updated_at)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(day, key) DO UPDATE SET
                        value = excluded.value,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (today, key.strip(), value.strip(), source, now),
                )

    def today_state(self) -> dict[str, str]:
        today = date.today().isoformat()
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT key, value FROM daily_state WHERE day = ?",
                (today,),
            ).fetchall()
        return {str(key): str(value) for key, value in rows}

    def add_emotional_pattern(self, label: str | None, intensity: float = 1.0) -> None:
        if not label or not label.strip():
            return
        try:
            intensity = float(intensity)
        except (TypeError, ValueError):
            intensity = 1.0
        intensity = max(0.1, min(intensity, 3.0))
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                row = conn.execute(
                    "SELECT weight, occurrences, last_seen FROM emotional_patterns WHERE label = ?",
                    (label.strip(),),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO emotional_patterns(label, weight, occurrences, last_seen, updated_at)
                        VALUES(?, ?, 1, ?, ?)
                        """,
                        (label.strip(), intensity, now, now),
                    )
                else:
                    previous_weight = self._decayed_weight(float(row[0]), str(row[2]))
                    conn.execute(
                        """
                        UPDATE emotional_patterns
                        SET weight = ?, occurrences = ?, last_seen = ?, updated_at = ?
                        WHERE label = ?
                        """,
                        (
                            min(previous_weight + intensity, 10.0),
                            int(row[1]) + 1,
                            now,
                            now,
                            label.strip(),
                        ),
                    )

    def emotional_patterns(self, limit: int = 5) -> list[dict[str, str | float | int]]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT label, weight, occurrences, last_seen, updated_at
                FROM emotional_patterns
                ORDER BY weight DESC, occurrences DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        patterns: list[dict[str, str | float | int]] = []
        for row in rows:
            item = dict(row)
            item["weight"] = round(self._decayed_weight(float(item["weight"]), str(item["last_seen"])), 2)
            patterns.append(item)
        return patterns

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

    @staticmethod
    def _decayed_weight(weight: float, last_seen: str) -> float:
        try:
            last_seen_date = datetime.fromisoformat(last_seen)
        except ValueError:
            return weight
        days = max(0, (datetime.now() - last_seen_date).days)
        return weight * (0.92**days)
