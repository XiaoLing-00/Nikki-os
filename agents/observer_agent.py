from __future__ import annotations

from datetime import datetime, timedelta

from config.preferences import PreferencesStore
from config.settings import Settings
from memory.long_memory import LongMemory


class ObserverAgent:
    def __init__(
        self,
        settings: Settings,
        long_memory: LongMemory,
        preferences: PreferencesStore | None = None,
    ) -> None:
        self.settings = settings
        self.long_memory = long_memory
        self._triggered: set[str] = set()
        self._last_casual_at: datetime | None = None
        self.preferences = preferences or PreferencesStore()

    def evaluate(self, context: dict) -> dict | None:
        preferences = self.preferences.load()
        now = datetime.now()
        if not preferences.proactive_enabled or self._in_quiet_hours(
            now.hour,
            preferences.quiet_start,
            preferences.quiet_end,
        ):
            return None
        app = context.get("app", "Unknown")
        interval_seconds = max(1, self.settings.observer_interval_ms // 1000)
        active_seconds = self.long_memory.touch_app(
            app,
            interval_seconds,
            reset_gap_minutes=self.settings.focus_gap_reset_minutes,
        )
        topic_text = " ".join(
            str(context.get(key, ""))
            for key in ("window_title", "topic", "vision_summary")
        ).lower()

        if preferences.trigger_greeting_enabled and 6 <= now.hour < 10 and f"morning_{now.date()}" not in self._triggered:
            self._triggered.add(f"morning_{now.date()}")
            return {
                "reason": "morning_greeting",
                "message": "现在是早晨，暖暖要自然地向用户问好，并轻轻询问今天安排。",
                "context_patch": {"user_status": "active", "topic": "早起问候"},
            }

        if preferences.trigger_late_night_enabled and (now.hour >= 23 or now.hour < 5) and f"late_night_{now.date()}" not in self._triggered:
            self._triggered.add(f"late_night_{now.date()}")
            return {
                "reason": "late_night",
                "message": "现在已经很晚了，暖暖要温柔地催用户休息，不要太严厉。",
                "context_patch": {"user_status": "tired", "topic": "深夜使用电脑"},
            }

        pet_y = context.get("pet_window_y")
        if preferences.trigger_position_enabled and isinstance(pet_y, int) and pet_y < 80:
            key = f"high_place_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "high_place",
                    "message": "暖暖发现自己被放到屏幕很高的位置，要用一点点害怕但可爱的语气提醒晓灵。",
                    "context_patch": {"user_status": "active", "topic": "桌宠窗口位置过高"},
                }

        if preferences.trigger_coding_enabled and app == "VS Code" and active_seconds >= self.settings.coding_minutes_threshold * 60:
            key = f"coding_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "long_coding",
                    "message": "用户已经连续使用 VS Code 较久，需要温柔安抚。",
                    "context_patch": {"user_status": "concentrated", "topic": "长时间编程"},
                }

        if preferences.trigger_interest_enabled and any(keyword in topic_text for keyword in ("手工", "服装", "衣服", "穿搭", "裁缝", "缝纫", "面料", "lolita", "洛丽塔", "fashion", "sewing")):
            key = f"craft_fashion_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "craft_fashion_interest",
                    "message": "用户正在看手工或服装相关内容，暖暖要表现出兴趣并轻松参与话题。",
                    "context_patch": {"user_status": "relaxed", "topic": "手工/服装内容"},
                }

        if preferences.trigger_relaxing_enabled and app == "Bilibili":
            key = f"bilibili_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "relaxing",
                    "message": "用户正在休闲看视频，暖暖可以轻松陪聊。",
                    "context_patch": {"user_status": "relaxed", "topic": "休闲娱乐"},
                }
        if preferences.trigger_casual_enabled and self._should_casual_chat(now):
            self._last_casual_at = now
            return {
                "reason": "casual_checkin",
                "message": "暖暖进行一次很短的无条件关怀，不要打扰用户，只说一句自然陪伴的话。",
                "context_patch": {"user_status": context.get("user_status", "active"), "topic": context.get("topic", "桌面陪伴")},
            }
        return None

    @staticmethod
    def _in_quiet_hours(hour: int, start: int, end: int) -> bool:
        start %= 24
        end %= 24
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _should_casual_chat(self, now: datetime) -> bool:
        if self._last_casual_at is None:
            self._last_casual_at = now
            return False
        return now - self._last_casual_at >= timedelta(minutes=self.settings.casual_chat_interval_minutes)
