from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import edge_tts

from config.preferences import PreferencesStore
from config.settings import Settings
from services.tts_service import TTSService


def test_edge_neural_voice_is_default_and_can_be_disabled(tmp_path, qtbot) -> None:
    del qtbot
    store = PreferencesStore(tmp_path / "preferences.json")
    service = TTSService(Settings(), store)

    assert service.mode == "edge"
    assert service.available
    store.update(speech_mode="off")
    assert service.mode == "off"
    assert not service.speak_system("这句话不应播放。")


def test_edge_tts_saves_audio_without_an_api_key(tmp_path, qtbot, monkeypatch) -> None:
    del qtbot
    store = PreferencesStore(tmp_path / "preferences.json")
    output = b"ID3 test audio"
    save = AsyncMock(side_effect=lambda path: Path(path).write_bytes(output))
    communicate = Mock(return_value=Mock(save=save))
    monkeypatch.setattr(edge_tts, "Communicate", communicate)
    service = TTSService(Settings(), store)

    path = service.synthesize_online("你好。")

    assert path is not None
    assert path.read_bytes() == output
    communicate.assert_called_once_with(
        "你好。",
        "zh-CN-XiaoxiaoNeural",
        rate="+0%",
        volume="+0%",
        pitch="+0Hz",
    )
    path.unlink()


def test_old_auto_mode_migrates_to_free_edge_tts(tmp_path, qtbot) -> None:
    del qtbot
    path = tmp_path / "preferences.json"
    path.write_text('{"speech_mode": "auto"}', encoding="utf-8")
    store = PreferencesStore(path)

    assert store.load().speech_mode == "edge"
    service = TTSService(Settings(), store)
    assert service._clean_text("  你好\n  暖暖  ") == "你好 暖暖"


def test_edge_failure_returns_none_for_system_fallback(tmp_path, qtbot, monkeypatch) -> None:
    del qtbot
    store = PreferencesStore(tmp_path / "preferences.json")
    save = AsyncMock(side_effect=ConnectionError("offline"))
    monkeypatch.setattr(edge_tts, "Communicate", Mock(return_value=Mock(save=save)))
    service = TTSService(Settings(), store)

    assert service.synthesize_online("断网时回退。") is None
