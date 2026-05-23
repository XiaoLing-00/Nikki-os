from __future__ import annotations

from datetime import datetime, timedelta

from config.settings import Settings
from memory.long_memory import LongMemory


class ObserverAgent:
    def __init__(self, settings: Settings, long_memory: LongMemory) -> None:
        self.settings = settings
        self.long_memory = long_memory
        self._triggered: set[str] = set()
        self._last_casual_at: datetime | None = None
        self._last_scene_id: str | None = None
        self._last_scene_prompt_at: datetime | None = None

    def evaluate(self, context: dict) -> dict | None:
        app = context.get("app", "Unknown")
        scene = context.get("scene") or {}
        scene_id = str(context.get("scene_id") or scene.get("id") or self._fallback_scene_id(context))
        scene_name = str(scene.get("name") or scene_id)
        proactive_level = str(scene.get("proactive_level") or "low")
        interval_seconds = max(1, self.settings.observer_interval_ms // 1000)
        active_seconds = self.long_memory.touch_app(
            f"scene:{scene_id}" if scene_id else app,
            interval_seconds,
            reset_gap_minutes=self.settings.focus_gap_reset_minutes,
        )
        now = datetime.now()
        topic_text = " ".join(
            str(context.get(key, ""))
            for key in ("window_title", "topic", "vision_summary")
        ).lower()
        task_context = self._task_context()

        if proactive_level == "silent" or scene_id in {"meeting", "game"}:
            self._last_scene_id = scene_id
            return None

        if 6 <= now.hour < 10 and f"morning_{now.date()}" not in self._triggered:
            self._triggered.add(f"morning_{now.date()}")
            return {
                "reason": "morning_greeting",
                "message": "现在是早晨，暖暖要自然地向用户问好，并轻轻询问今天安排。",
                "context_patch": {"user_status": "active", "topic": "早起问候"},
            }

        if (now.hour >= 23 or now.hour < 5) and f"late_night_{now.date()}" not in self._triggered:
            self._triggered.add(f"late_night_{now.date()}")
            return {
                "reason": "late_night",
                "message": "现在已经很晚了，暖暖要关心 00 休息，并轻轻提醒近期要忙的事情。",
                "context_patch": {"user_status": "tired", "topic": "深夜使用电脑", **task_context},
            }

        pet_y = context.get("pet_window_y")
        if isinstance(pet_y, int) and pet_y < 80:
            key = f"high_place_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "high_place",
                    "message": "暖暖发现自己被放到屏幕很高的位置，要自然地提醒 00。",
                    "context_patch": {"user_status": "active", "topic": "桌宠窗口位置过高"},
                }

        if scene_id in {"coding", "paper_writing", "research", "ppt_defense", "ai_chat"} and active_seconds >= self.settings.coding_minutes_threshold * 60:
            key = f"work_{scene_id}_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "long_work",
                    "message": f"00 已经在“{scene_name}”场景里连续工作一小时，暖暖要温柔提醒休息，并可以提一句稍后继续当前任务。",
                    "context_patch": {"user_status": "concentrated", "topic": f"长时间{scene_name}", "scene_id": scene_id, **task_context},
                }

        if scene_id == "error_debug":
            key = f"error_debug_{now.date()}_{self._scene_bucket(now)}"
            if key not in self._triggered:
                self._triggered.add(key)
                self._last_scene_id = scene_id
                return {
                    "reason": "error_debug",
                    "message": "00 当前可能遇到了报错或崩溃，暖暖要先安慰，再直接提醒可以从最后几行错误信息看起。",
                    "context_patch": {"user_status": "concentrated", "topic": "报错/调试", "scene_id": scene_id},
                }

        if self._scene_changed(scene_id, now):
            self._last_scene_id = scene_id
            self._last_scene_prompt_at = now
            return {
                "reason": "scene_change",
                "message": f"00 切换到了“{scene_name}”场景，暖暖要根据这个场景说一句自然、克制的陪伴话，不要模板化。",
                "context_patch": {"user_status": scene.get("user_status", context.get("user_status", "active")), "topic": scene_name, "scene_id": scene_id},
            }

        if any(keyword in topic_text for keyword in ("手工", "服装", "衣服", "穿搭", "裁缝", "缝纫", "面料", "lolita", "洛丽塔", "fashion", "sewing")):
            key = f"craft_fashion_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "craft_fashion_interest",
                    "message": "用户正在看手工或服装相关内容，暖暖要表现出兴趣并轻松参与话题。",
                    "context_patch": {"user_status": "relaxed", "topic": "手工/服装内容"},
                }

        if scene_id == "video_relax":
            key = f"bilibili_{now.date()}"
            if key not in self._triggered:
                self._triggered.add(key)
                return {
                    "reason": "video_relax",
                    "message": "00 正在看视频或放松，暖暖可以陪着看，不要扫兴；如果任务记忆里有急迫任务，只轻轻提一句稍后回去接上。",
                    "context_patch": {"user_status": "relaxed", "topic": "休闲娱乐", "scene_id": scene_id, **task_context},
                }
        if self._should_casual_chat(now):
            self._last_casual_at = now
            return {
                "reason": "casual_checkin",
                "message": "暖暖进行一次很短的无条件关怀，不要打扰用户，只说一句自然陪伴的话。",
                "context_patch": {"user_status": context.get("user_status", "active"), "topic": context.get("topic", "桌面陪伴")},
            }
        return None

    @staticmethod
    def _fallback_scene_id(context: dict) -> str:
        app = context.get("app")
        if app == "VS Code":
            return "coding"
        if app == "Bilibili":
            return "video_relax"
        if app == "Word":
            return "paper_writing"
        if app == "PowerPoint":
            return "ppt_defense"
        if app == "Browser":
            return "research"
        return "daily_unknown"

    def _task_context(self) -> dict:
        current_task = None
        if hasattr(self.long_memory, "current_task"):
            current_task = self.long_memory.current_task()
        return {"current_task": current_task} if current_task else {}

    def _scene_changed(self, scene_id: str, now: datetime) -> bool:
        if scene_id in {"daily_unknown", "meeting", "game"}:
            return False
        if self._last_scene_id is None:
            self._last_scene_id = scene_id
            return False
        if scene_id == self._last_scene_id:
            return False
        if self._last_scene_prompt_at and now - self._last_scene_prompt_at < timedelta(minutes=self.settings.casual_chat_interval_minutes):
            return False
        return True

    @staticmethod
    def _scene_bucket(now: datetime) -> str:
        return f"{now.hour:02d}_{now.minute // 15}"

    def _should_casual_chat(self, now: datetime) -> bool:
        if self._last_casual_at is None:
            self._last_casual_at = now
            return False
        return now - self._last_casual_at >= timedelta(minutes=self.settings.casual_chat_interval_minutes)
