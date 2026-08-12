from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from config.preferences import PreferencesStore
from config.settings import Settings
from perception.screen_capture import (
    capture_primary_screen,
    classify_app,
    get_active_process_name,
    get_active_window_title,
)
from services.llm_service import LLMService


class ContextBuilder:
    def __init__(
        self,
        settings: Settings,
        llm_service: LLMService | None = None,
        preferences: PreferencesStore | None = None,
    ) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.preferences = preferences or PreferencesStore()

    def build_low_frequency_context(self) -> dict:
        title = get_active_window_title()
        process_name = get_active_process_name()
        app = classify_app(title, process_name)
        preferences = self.preferences.load()
        excluded = any(
            item.lower() in f"{app} {title} {process_name}".lower()
            for item in preferences.excluded_apps
            if item.strip()
        )
        if preferences.perception_mode == "off":
            app, title, process_name = "Hidden", "", ""
        elif excluded:
            app, title, process_name = "Sensitive", "", ""
        elif preferences.perception_mode == "app_only":
            title = ""
        return {
            "app": app,
            "process_name": process_name,
            "window_title": title,
            "topic": self._topic_from_title(title),
            "user_status": self._status_from_app(app, process_name),
            "perception_mode": preferences.perception_mode,
            "redacted": excluded,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

    def capture_for_preview(self) -> Path | None:
        context = self.build_low_frequency_context()
        if not self.preferences.load().vision_enabled or context.get("redacted"):
            return None
        handle = NamedTemporaryFile(prefix="soulpet_screen_", suffix=".png", delete=False)
        image_path = Path(handle.name)
        handle.close()
        return capture_primary_screen(image_path)

    def build_visual_context(self, approved_image_path: Path | None = None) -> dict:
        context = self.build_low_frequency_context()
        if not self.preferences.load().vision_enabled:
            context["perception_mode"] = "vision_disabled"
            context["vision_summary"] = "用户尚未在隐私设置中启用截图分析。"
            return context
        if context.get("redacted"):
            context["perception_mode"] = "vision_blocked_sensitive_app"
            context["vision_summary"] = "当前应用位于敏感应用排除名单，未进行截图。"
            return context
        image_path = approved_image_path
        if image_path is None:
            handle = NamedTemporaryFile(prefix="soulpet_screen_", suffix=".png", delete=False)
            image_path = Path(handle.name)
            handle.close()
            image_path = capture_primary_screen(image_path)
        context["perception_mode"] = "vision"
        context["screenshot"] = "temporary" if image_path else ""

        try:
            if image_path and self.llm_service:
                context["vision_summary"] = self.llm_service.describe_image(
                    Path(image_path),
                    (
                        "请用中文概括当前屏幕内容，判断用户在做什么、主题是什么。"
                        "如果看到手工、服装、穿搭、绘画、代码或视频内容，请明确指出。"
                        "是否适合桌宠主动回应。输出 80 字以内。"
                    ),
                )
                context["topic"] = context.get("vision_summary") or context["topic"]
        finally:
            if image_path:
                Path(image_path).unlink(missing_ok=True)
        return context

    @staticmethod
    def _topic_from_title(title: str) -> str:
        if not title:
            return "未知任务"
        title = title.replace(" - Visual Studio Code", "").replace(" - Microsoft Edge", "")
        return title[:80]

    @staticmethod
    def _status_from_app(app: str, process_name: str = "") -> str:
        process = process_name.lower()
        if app == "VS Code" or process in {"code.exe", "pycharm64.exe", "idea64.exe"}:
            return "concentrated"
        if app == "Bilibili" or process in {"bilibili.exe", "cloudmusic.exe", "vlc.exe"}:
            return "relaxed"
        if app == "Unknown":
            return "idle"
        return "active"
