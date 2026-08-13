from __future__ import annotations

from unittest.mock import Mock

import requests

from config.settings import Settings
from services.llm_service import LLMService

VALID_PAYLOAD = {
    "context": {"app": "VS Code"},
    "response": {"text": "晓灵，今天也一起加油呀。", "emotion": "wink", "action": "motion_talk"},
    "memory_update": {"key_info": "", "sentiment": "neutral"},
}


def test_dashscope_http_contract_and_json_validation(monkeypatch) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": __import__("json").dumps(VALID_PAYLOAD)}}]
    }
    service = LLMService(Settings(dashscope_api_key="test-only-key", request_retries=0))
    post = Mock(return_value=response)
    monkeypatch.setattr(service._session, "post", post)

    result = service.chat_json("system", "user")

    assert result == VALID_PAYLOAD
    call = post.call_args
    assert call.args[0].endswith("/chat/completions")
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-only-key"
    assert call.kwargs["json"]["response_format"] == {"type": "json_object"}
    assert call.kwargs["json"]["enable_thinking"] is False
    assert call.kwargs["json"]["max_tokens"] == 384
    assert call.kwargs["timeout"] == service.settings.request_timeout


def test_dashscope_failure_retries_then_returns_safe_fallback(monkeypatch) -> None:
    service = LLMService(Settings(dashscope_api_key="test-only-key", request_retries=1))
    post = Mock(side_effect=requests.Timeout("offline"))
    monkeypatch.setattr(service._session, "post", post)

    result = service.chat_json("system", "user")

    assert post.call_count == 2
    assert result["response"]["emotion"] == "awkward"
    assert result["response"]["action"] == "motion_idle"
    assert result["memory_update"]["key_info"] == ""


def test_flash_emotion_synonym_is_repaired_before_validation(monkeypatch) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    payload = {
        **VALID_PAYLOAD,
        "response": {**VALID_PAYLOAD["response"], "emotion": "excited"},
    }
    response.json.return_value = {
        "choices": [{"message": {"content": __import__("json").dumps(payload)}}]
    }
    service = LLMService(Settings(dashscope_api_key="test-only-key", request_retries=0))
    monkeypatch.setattr(service._session, "post", Mock(return_value=response))

    result = service.chat_json("system", "user")

    assert result["response"]["emotion"] == "happy"
