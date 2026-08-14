from __future__ import annotations

import tempfile
import threading
import wave
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from config.settings import Settings
from utils.logger import get_logger


class ASRService:
    """Record a short microphone clip and transcribe it with DashScope ASR."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self._recording = False
        self._recording_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._frames: list[bytes] = []
        self._record_error: Exception | None = None
        self._audio = None
        self._stream = None

    @property
    def available(self) -> bool:
        return bool(self.settings.dashscope_api_key)

    def listen_once(self) -> str:
        if not self.available:
            return "未配置 DASHSCOPE_API_KEY，语音识别暂时不可用呀。"

        wav_path: Path | None = None
        try:
            wav_path = self._record_temp_wav()
            return self._transcribe_file(wav_path).strip()
        except Exception as exc:
            self.logger.exception("ASR failed: %s", exc)
            return "唔，暖暖刚刚没听清，可以再说一次吗？"
        finally:
            if wav_path:
                wav_path.unlink(missing_ok=True)

    @property
    def recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        if not self.available:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY，语音识别暂时不可用。")
        if self._recording:
            return
        try:
            import pyaudio
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("PyAudio is required for microphone recording") from exc

        self._frames = []
        self._record_error = None
        self._stop_event = threading.Event()
        self._audio = pyaudio.PyAudio()
        try:
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.settings.asr_sample_rate,
                input=True,
                frames_per_buffer=1024,
            )
        except Exception:
            self._audio.terminate()
            self._audio = None
            self._stream = None
            raise

        self._recording = True
        self._recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._recording_thread.start()

    def stop_and_transcribe(self) -> str:
        if not self._recording and not self._frames:
            return "唔，暖暖还没有开始录音呀。"

        if self._stop_event:
            self._stop_event.set()
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=3)
        self._cleanup_input()
        self._recording = False

        if self._record_error:
            self.logger.exception("ASR recording failed: %s", self._record_error)
            return "唔，麦克风没有准备好。请确认系统允许 python.exe 使用麦克风。"
        if not self._frames:
            return "唔，暖暖没有录到声音，可以再试一次吗？"

        wav_path: Path | None = None
        try:
            wav_path = self._write_temp_wav(self._frames)
            return self._transcribe_file(wav_path).strip()
        except Exception as exc:
            self.logger.exception("ASR failed: %s", exc)
            return "唔，暖暖刚刚没听清，可以再说一次吗？"
        finally:
            self._frames = []
            if wav_path:
                wav_path.unlink(missing_ok=True)

    def _record_loop(self) -> None:
        try:
            while self._stop_event and not self._stop_event.is_set():
                self._frames.append(self._stream.read(1024, exception_on_overflow=False))
        except Exception as exc:
            self._record_error = exc
        finally:
            self._recording = False
            self._cleanup_input()

    def _record_temp_wav(self) -> Path:
        try:
            import pyaudio
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("PyAudio is required for microphone recording") from exc

        chunk = 1024
        channels = 1
        sample_rate = self.settings.asr_sample_rate
        frame_count = int(sample_rate / chunk * self.settings.asr_record_seconds)
        audio = pyaudio.PyAudio()
        stream = None
        frames: list[bytes] = []
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk,
            )
            for _ in range(frame_count):
                frames.append(stream.read(chunk, exception_on_overflow=False))
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            audio.terminate()

        return self._write_temp_wav(frames)

    def _write_temp_wav(self, frames: list[bytes]) -> Path:
        handle = tempfile.NamedTemporaryFile(prefix="soulpet_asr_", suffix=".wav", delete=False)
        wav_path = Path(handle.name)
        handle.close()
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.settings.asr_sample_rate)
            wav_file.writeframes(b"".join(frames))
        return wav_path

    def _cleanup_input(self) -> None:
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._audio:
            try:
                self._audio.terminate()
            except Exception:
                pass
            self._audio = None

    def _transcribe_file(self, wav_path: Path) -> str:
        try:
            import dashscope
            from dashscope.audio.asr import Recognition, RecognitionCallback
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("dashscope package is required for ASR") from exc

        class _Callback(RecognitionCallback):
            pass

        dashscope.api_key = self.settings.dashscope_api_key
        http_api_url, websocket_api_url = self._dashscope_sdk_urls()
        dashscope.base_http_api_url = http_api_url
        dashscope.base_websocket_api_url = websocket_api_url
        recognition = Recognition(
            model=self.settings.asr_model,
            callback=_Callback(),
            format="wav",
            sample_rate=self.settings.asr_sample_rate,
        )
        result = recognition.call(str(wav_path))
        text = self._extract_text(result)
        if text:
            return text
        self.logger.error("Unrecognized ASR response: %s", result)
        status_code = getattr(result, "status_code", None)
        code = getattr(result, "code", None)
        message = getattr(result, "message", None)
        if status_code and int(status_code) >= 400:
            raise RuntimeError(f"{status_code} {code or ''} {message or ''}".strip())
        raise RuntimeError("empty ASR result")

    def _dashscope_sdk_urls(self) -> tuple[str, str]:
        """Keep DashScope SDK speech calls in the same region as chat calls."""
        parsed = urlsplit(self.settings.dashscope_base_url)
        http_api_url = urlunsplit((parsed.scheme or "https", parsed.netloc, "/api/v1", "", ""))
        websocket_api_url = urlunsplit(
            ("wss", parsed.netloc, "/api-ws/v1/inference", "", "")
        )
        return http_api_url, websocket_api_url

    @staticmethod
    def _extract_text(result) -> str:
        if isinstance(result, dict):
            output = result.get("output") or {}
            if isinstance(output, dict):
                sentence = output.get("sentence")
                if isinstance(sentence, list):
                    text = "".join(str(item.get("text", "")) for item in sentence if isinstance(item, dict))
                elif isinstance(sentence, dict):
                    text = sentence.get("text", "")
                else:
                    text = output.get("text", "")
                if text:
                    return str(text)
            return ""

        if hasattr(result, "get_sentence"):
            sentence = result.get_sentence()
            if isinstance(sentence, list):
                return "".join(str(item.get("text", "")) for item in sentence if isinstance(item, dict)).strip()
            if isinstance(sentence, dict):
                return str(sentence.get("text", "")).strip()

        output = getattr(result, "output", None)
        if isinstance(output, dict):
            sentence = output.get("sentence")
            if isinstance(sentence, list):
                text = "".join(str(item.get("text", "")) for item in sentence if isinstance(item, dict))
                if text:
                    return text
            if isinstance(sentence, dict) and sentence.get("text"):
                return str(sentence["text"])
            if output.get("text"):
                return str(output["text"])
        return ""
