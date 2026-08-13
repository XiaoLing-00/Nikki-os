from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from PyQt6.QtWidgets import QApplication

from agents.persona_agent import PersonaAgent
from config.preferences import PreferencesStore
from config.settings import get_settings
from memory.long_memory import LongMemory
from memory.short_memory import ShortMemory
from services.asr_service import ASRService
from services.llm_service import LLMService
from services.tts_service import TTSService


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_online_services(output_path: Path, asr_wav: Path | None = None) -> dict:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY was not loaded")

    app = QApplication.instance() or QApplication(["nikki-online-validation"])

    with tempfile.TemporaryDirectory(prefix="nikki_online_validation_") as temporary:
        temporary_root = Path(temporary)
        llm_service = LLMService(settings)
        agent = PersonaAgent(
            llm_service,
            ShortMemory(max_turns=4),
            LongMemory(temporary_root / "memory.sqlite3"),
        )

        chat_started = perf_counter()
        result = agent.reply(
            "请用一句简短中文向晓灵问好。",
            {"app": "Windows validation", "topic": "online smoke test", "user_status": "active"},
        )
        chat_latency_ms = round((perf_counter() - chat_started) * 1000, 1)
        response = result["response"]
        if not response["text"].strip() or "晓灵" not in response["text"]:
            raise RuntimeError("Persona response did not satisfy the expected contract")

        preference_store = PreferencesStore(temporary_root / "preferences.json")
        preference_store.update(speech_mode="edge")
        tts_service = TTSService(settings, preference_store)
        tts_started = perf_counter()
        audio_path = tts_service.synthesize_online("晓灵你好，这是暖暖的 Windows 语音测试。")
        tts_latency_ms = round((perf_counter() - tts_started) * 1000, 1)
        if audio_path is None or not audio_path.exists() or audio_path.stat().st_size < 1000:
            raise RuntimeError("Edge TTS did not produce a valid audio file")
        audio_size = audio_path.stat().st_size
        audio_sha256 = _sha256(audio_path)
        audio_path.unlink(missing_ok=True)
        tts_service.stop()
        app.processEvents()

        asr_report: dict[str, object] = {"tested": False}
        if asr_wav is not None:
            if not asr_wav.exists() or asr_wav.stat().st_size < 1000:
                raise RuntimeError("ASR fixture WAV is missing or empty")
            asr_started = perf_counter()
            transcript = ASRService(settings)._transcribe_file(asr_wav).strip()
            asr_latency_ms = round((perf_counter() - asr_started) * 1000, 1)
            if not transcript:
                raise RuntimeError("DashScope ASR returned an empty transcript")
            asr_report = {
                "tested": True,
                "model": settings.asr_model,
                "latency_ms": asr_latency_ms,
                "transcript_characters": len(transcript),
                "fixture_sha256": _sha256(asr_wav),
            }

    report = {
        "validated_at": datetime.now(UTC).isoformat(),
        "platform": "Windows",
        "source_commit": _source_commit(),
        "secrets_recorded": False,
        "chat": {
            "provider": "DashScope",
            "model": settings.text_model,
            "thinking": False,
            "latency_ms": chat_latency_ms,
            "reply_characters": len(response["text"]),
            "emotion": response["emotion"],
            "action": response["action"],
        },
        "tts": {
            "provider": "Edge Neural TTS",
            "voice": preference_store.load().speech_voice,
            "latency_ms": tts_latency_ms,
            "audio_size_bytes": audio_size,
            "audio_sha256": audio_sha256,
            "temporary_audio_deleted": True,
        },
        "asr": asr_report,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Nikki OS online chat, TTS, and optional ASR")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asr-wav", type=Path)
    args = parser.parse_args()
    report = validate_online_services(args.output, args.asr_wav)
    print(
        json.dumps(
            {
                "result": "pass",
                "chat_latency_ms": report["chat"]["latency_ms"],
                "tts_latency_ms": report["tts"]["latency_ms"],
                "asr_latency_ms": report["asr"].get("latency_ms"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
