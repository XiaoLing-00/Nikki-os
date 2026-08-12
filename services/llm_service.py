from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import requests

from config.settings import Settings
from services.response_contract import ResponseContractError, validate_response
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
                "text": "唔，暖暖现在还没有连上大脑哒。请检查 DASHSCOPE_API_KEY 呀。",
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
        last_error: Exception | None = None
        for attempt in range(self.settings.request_retries + 1):
            try:
                content = self._post_chat(self.settings.text_model, messages, json_mode=True)
                return validate_response(self._extract_json(content))
            except (requests.RequestException, KeyError, ValueError, ResponseContractError) as exc:
                last_error = exc
                self.logger.warning(
                    "DashScope text attempt %s/%s failed: %s",
                    attempt + 1,
                    self.settings.request_retries + 1,
                    type(exc).__name__,
                )
        self.logger.error("DashScope text call exhausted retries: %s", last_error)
        fallback["response"]["text"] = "呜，暖暖刚刚思考卡住了，但我还在晓灵身边呀。"
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

    def _post_chat(self, model: str, messages: list[dict], json_mode: bool = False) -> str:
        url = f"{self.settings.dashscope_base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.75,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
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
