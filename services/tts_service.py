from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import edge_tts
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtTextToSpeech import QTextToSpeech

from config.preferences import PreferencesStore
from config.settings import Settings
from utils.logger import get_logger
from utils.metrics import record_metric


class TTSService(QObject):
    """Speak replies with free Edge neural TTS and an offline system fallback."""

    online_requested = pyqtSignal(str)

    def __init__(
        self,
        settings: Settings,
        preferences: PreferencesStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.preferences = preferences
        self.logger = get_logger(__name__)
        self._speech = QTextToSpeech(self)
        self._select_chinese_voice()
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.75)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._current_audio: Path | None = None
        self.online_requested.connect(self._play_online_result)

    @property
    def mode(self) -> str:
        return self.preferences.load().speech_mode

    @property
    def available(self) -> bool:
        return self.mode == "edge" or (
            self.mode == "system" and self._speech.state() != QTextToSpeech.State.Error
        )

    def stop(self) -> None:
        self._speech.stop()
        self._player.stop()
        self._player.setSource(QUrl())
        self._remove_current_audio()

    def speak_system(self, text: str) -> bool:
        clean = self._clean_text(text)
        if not clean or self.mode == "off" or self._speech.state() == QTextToSpeech.State.Error:
            return False
        self.stop()
        self._speech.say(clean)
        record_metric("tts_reply", provider="system", success=True, characters=len(clean))
        return True

    def synthesize_online(self, text: str) -> Path | None:
        """Generate Edge neural speech in a worker thread without an API key."""
        clean = self._clean_text(text)
        preferences = self.preferences.load()
        if not clean or preferences.speech_mode != "edge":
            return None
        handle = tempfile.NamedTemporaryFile(prefix="nikki_edge_tts_", suffix=".mp3", delete=False)
        path = Path(handle.name)
        handle.close()
        try:
            rate = f"{preferences.speech_rate:+d}%"
            synthesis = edge_tts.Communicate(
                clean,
                preferences.speech_voice,
                rate=rate,
                volume="+0%",
                pitch="+0Hz",
            )
            asyncio.run(asyncio.wait_for(synthesis.save(str(path)), timeout=min(15, self.settings.request_timeout)))
            if path.stat().st_size == 0:
                raise RuntimeError("Edge TTS returned empty audio")
            record_metric(
                "tts_reply",
                provider="edge",
                success=True,
                characters=len(clean),
                voice=preferences.speech_voice,
            )
            return path
        except Exception as exc:
            path.unlink(missing_ok=True)
            self.logger.warning("Edge TTS failed; using system voice: %s", type(exc).__name__)
            record_metric("tts_reply", provider="edge", success=False, code=type(exc).__name__)
            return None

    def play_online_or_fallback(self, text: str, audio_path: Path | None) -> None:
        """Queue playback back onto the Qt UI thread."""
        marker = f"{audio_path or ''}\n{text}"
        self.online_requested.emit(marker)

    def _play_online_result(self, marker: str) -> None:
        path_text, text = marker.split("\n", 1)
        if self.mode == "off":
            if path_text:
                Path(path_text).unlink(missing_ok=True)
            return
        if not path_text:
            self.speak_system(text)
            return
        path = Path(path_text)
        if not path.exists():
            self.speak_system(text)
            return
        self.stop()
        self._current_audio = path
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status in {QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia}:
            self._player.setSource(QUrl())
            self._remove_current_audio()

    def _remove_current_audio(self) -> None:
        if self._current_audio:
            try:
                self._current_audio.unlink(missing_ok=True)
            except OSError:
                self.logger.debug("TTS temporary audio is still held by the media backend")
            self._current_audio = None

    def _select_chinese_voice(self) -> None:
        voices = list(self._speech.availableVoices())
        preferred = next(
            (
                voice
                for voice in voices
                if voice.locale().name().startswith("zh_CN") and voice.name().lower() in {"tingting", "xiaoxiao"}
            ),
            None,
        )
        chinese = preferred or next((voice for voice in voices if voice.locale().name().startswith("zh")), None)
        if chinese:
            self._speech.setVoice(chinese)
        self._speech.setRate(0.0)
        self._speech.setPitch(0.0)
        self._speech.setVolume(0.85)

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(str(text).strip().split())[:600]
