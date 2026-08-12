from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from config.settings import BASE_DIR


@dataclass(frozen=True)
class UserPreferences:
    renderer_backend: str = "sprite"
    perception_mode: str = "app_only"
    vision_enabled: bool = False
    proactive_enabled: bool = True
    trigger_greeting_enabled: bool = True
    trigger_late_night_enabled: bool = True
    trigger_coding_enabled: bool = True
    trigger_relaxing_enabled: bool = True
    trigger_interest_enabled: bool = True
    trigger_position_enabled: bool = True
    trigger_casual_enabled: bool = True
    quiet_start: int = 23
    quiet_end: int = 7
    excluded_apps: tuple[str, ...] = ("1Password", "KeePass", "Bitwarden", "银行", "支付")
    remember_window_position: bool = True
    window_x: int | None = None
    window_y: int | None = None
    auto_start: bool = False


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or BASE_DIR / "data" / "preferences.json"

    def load(self) -> UserPreferences:
        if not self.path.exists():
            return UserPreferences()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {item.name for item in fields(UserPreferences)}
            clean = {key: value for key, value in payload.items() if key in allowed}
            if isinstance(clean.get("excluded_apps"), list):
                clean["excluded_apps"] = tuple(str(item) for item in clean["excluded_apps"])
            result = UserPreferences(**clean)
            if result.renderer_backend not in {"sprite", "live2d"}:
                raise ValueError("invalid renderer_backend")
            if result.perception_mode not in {"off", "app_only", "window_title"}:
                raise ValueError("invalid perception_mode")
            return result
        except Exception:
            return UserPreferences()

    def save(self, preferences: UserPreferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(preferences), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def update(self, **changes) -> UserPreferences:
        payload = asdict(self.load())
        payload.update(changes)
        if isinstance(payload.get("excluded_apps"), list):
            payload["excluded_apps"] = tuple(payload["excluded_apps"])
        result = UserPreferences(**payload)
        self.save(result)
        return result
