from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def load_env_file(path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    env_path = path or BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    app_name: str = "SoulPet-OS"
    persona_name: str = "苏暖暖"
    dashscope_api_key: str | None = None
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    text_model: str = "qwen3.6-flash"
    vision_model: str = "qwen3.7-plus"
    asr_model: str = "paraformer-realtime-v2"
    request_timeout: int = 20
    request_retries: int = 0
    reply_visible_seconds: int = 20
    asr_record_seconds: int = 5
    asr_sample_rate: int = 16_000
    asr_max_record_seconds: int = 30
    short_memory_turns: int = 15
    observer_interval_ms: int = 10_000
    idle_state_interval_ms: int = 60_000
    casual_chat_interval_minutes: int = 20
    coding_minutes_threshold: int = 45
    focus_gap_reset_minutes: int = 5
    max_long_memories: int = 500
    database_path: Path = BASE_DIR / "data" / "soulpet.sqlite3"
    screenshot_path: Path = BASE_DIR / "data" / "latest_screen.png"
    live2d_viewer_path: Path = BASE_DIR / "assets" / "live2d" / "viewer.html"
    live2d_model_path: Path = BASE_DIR / "assets" / "live2d" / "nikki" / "model3.json"
    live2d_actions_path: Path = BASE_DIR / "assets" / "live2d" / "actions.json"
    sprite_manifest_path: Path = BASE_DIR / "assets" / "sprites" / "nuannuan" / "manifest.json"
    renderer_backend: str = "sprite"
    env_file_path: Path | None = None


def get_settings() -> Settings:
    env_file = BASE_DIR / ".env"
    fallback_env_file = BASE_DIR / "env"
    loaded_env_file = env_file if env_file.exists() else fallback_env_file if fallback_env_file.exists() else None
    if loaded_env_file:
        load_env_file(loaded_env_file)
    from config.preferences import PreferencesStore

    saved_renderer = PreferencesStore().load().renderer_backend
    renderer_backend = os.getenv("SOULPET_RENDERER", saved_renderer).strip().lower()
    if renderer_backend not in {"sprite", "live2d"}:
        renderer_backend = "sprite"
    dashscope_base_url = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).rstrip("/")
    international_endpoint = (
        "dashscope-intl.aliyuncs.com" in dashscope_base_url
        or ".ap-southeast-1.maas.aliyuncs.com" in dashscope_base_url
    )
    default_asr_model = "fun-asr-realtime" if international_endpoint else "paraformer-realtime-v2"
    return Settings(
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
        dashscope_base_url=dashscope_base_url,
        text_model=os.getenv("SOULPET_TEXT_MODEL", "qwen3.6-flash"),
        vision_model=os.getenv("SOULPET_VISION_MODEL", "qwen3.7-plus"),
        asr_model=os.getenv("SOULPET_ASR_MODEL", default_asr_model),
        asr_record_seconds=int(os.getenv("SOULPET_ASR_RECORD_SECONDS", "5")),
        asr_sample_rate=int(os.getenv("SOULPET_ASR_SAMPLE_RATE", "16000")),
        asr_max_record_seconds=max(5, min(120, int(os.getenv("SOULPET_ASR_MAX_RECORD_SECONDS", "30")))),
        request_timeout=int(os.getenv("SOULPET_REQUEST_TIMEOUT", "20")),
        request_retries=max(0, min(3, int(os.getenv("SOULPET_REQUEST_RETRIES", "0")))),
        reply_visible_seconds=max(8, min(120, int(os.getenv("SOULPET_REPLY_VISIBLE_SECONDS", "20")))),
        max_long_memories=max(20, int(os.getenv("SOULPET_MAX_LONG_MEMORIES", "500"))),
        renderer_backend=renderer_backend,
        env_file_path=loaded_env_file,
    )
