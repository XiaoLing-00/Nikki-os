from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import requests

from config.settings import Settings
from utils.logger import get_logger


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)

    @property
    def available(self) -> bool:
        return bool(self.settings.dashscope_api_key)

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        fallback = {
            "context": {},
            "response": {
                "text": "暖暖现在还没有连上大脑。请检查 DASHSCOPE_API_KEY。",
                "emotion": "awkward",
                "action": "motion_idle",
            },
            "memory_update": {"key_info": "", "sentiment": "neutral"},
        }
        if not self.available:
            return fallback

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_prompt})
        try:
            content = self._post_chat(self.settings.text_model, messages)
            return self._extract_json(content)
        except Exception as exc:
            self.logger.exception("DashScope text call failed: %s", exc)
            fallback["response"]["text"] = "暖暖刚刚思考卡住了，但我还在 00 身边。"
            return fallback

    def describe_image(self, image_path: Path, prompt: str) -> str:
        if not self.available:
            return "未配置 DASHSCOPE_API_KEY，视觉识别暂不可用。"
        try:
            image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                    ],
                }
            ]
            return self._post_chat(self.settings.vision_model, messages).strip()
        except Exception as exc:
            self.logger.exception("DashScope vision call failed: %s", exc)
            return "视觉识别失败，暖暖只看到了一个模糊的屏幕印象。"

    def _post_chat(self, model: str, messages: list[dict]) -> str:
        url = f"{self.settings.dashscope_base_url}/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.75,
            },
            timeout=self.settings.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json\n", "", 1).replace("JSON\n", "", 1)
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]
        return json.loads(content)
