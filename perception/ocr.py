from __future__ import annotations

from pathlib import Path

from services.llm_service import LLMService


class VisionRecognizer:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def describe_screen(self, image_path: Path, app: str, title: str) -> str:
        prompt = (
            "你是 SoulPet-OS 的屏幕感知模块。请简洁描述截图中用户正在做什么，"
            "尤其关注应用、内容主题、用户可能状态。不要输出隐私敏感推断。"
            f"\n当前窗口应用：{app}\n窗口标题：{title}"
        )
        return self.llm_service.describe_image(image_path, prompt)
