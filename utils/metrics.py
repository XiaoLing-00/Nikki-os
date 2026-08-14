from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from config.settings import BASE_DIR

_LOCK = Lock()


def record_metric(event: str, *, path: Path | None = None, **values: object) -> None:
    target = path or BASE_DIR / "data" / "metrics.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(UTC).isoformat(), "event": event, **values}
    with _LOCK, target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
