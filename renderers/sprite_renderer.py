from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QWidget

from animation.states import AnimationState


class SpriteRenderer(QWidget):
    def __init__(self, manifest_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.manifest_path = manifest_path
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.atlas = QImage(str(manifest_path.parent / self.manifest["atlas"]))
        if self.atlas.isNull():
            raise RuntimeError(f"cannot load sprite atlas: {manifest_path.parent / self.manifest['atlas']}")
        self._state = AnimationState.IDLE.value
        self._frame = 0
        self._custom_path: Path | None = None
        self._custom_strip = QImage()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_state(AnimationState.IDLE, "wink", "motion_idle")

    def play_state(self, state: AnimationState, emotion: str, action: str) -> None:
        del emotion, action
        requested = state.value
        if requested not in self.manifest["states"]:
            requested = AnimationState.IDLE.value
        if requested != self._state:
            self._frame = 0
        self._state = requested
        self._load_custom_strip()
        fps = max(1, int(self._config().get("fps", self.manifest.get("default_fps", 8))))
        self._timer.start(round(1000 / fps))
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        self._draw_current_frame(painter)

    def render_current_frame(self, background: QColor | None = None) -> QImage:
        """Render deterministically without grabbing a transparent native window."""
        output = QImage(
            self.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        output.fill(background or QColor(0, 0, 0, 0))
        painter = QPainter(output)
        self._draw_current_frame(painter)
        painter.end()
        return output

    def _draw_current_frame(self, painter: QPainter) -> None:
        config = self._config()
        cell_w = int(self.manifest["cell_width"])
        cell_h = int(self.manifest["cell_height"])
        image = self._custom_strip if not self._custom_strip.isNull() else self.atlas
        source = QRectF(
            self._frame * cell_w,
            0 if not self._custom_strip.isNull() else int(config.get("row", 0)) * cell_h,
            cell_w,
            cell_h,
        )
        scale = min(self.width() / cell_w, self.height() / cell_h)
        target_w = cell_w * scale
        target_h = cell_h * scale
        target = QRectF((self.width() - target_w) / 2, self.height() - target_h, target_w, target_h)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(target, image, source)

    def _next_frame(self) -> None:
        config = self._config()
        frame_count = max(1, int(config["frames"]))
        self._frame += 1
        if self._frame >= frame_count:
            if config.get("loop", False):
                self._frame = 0
            else:
                next_state = str(config.get("next", AnimationState.IDLE.value))
                self._state = next_state if next_state in self.manifest["states"] else AnimationState.IDLE.value
                self._frame = 0
                self._load_custom_strip()
                fps = max(1, int(self._config().get("fps", 8)))
                self._timer.start(round(1000 / fps))
        self.update()

    def _config(self) -> dict:
        return self.manifest["states"].get(self._state, self.manifest["states"][AnimationState.IDLE.value])

    def _load_custom_strip(self) -> None:
        relative = self._config().get("strip")
        path = self.manifest_path.parent / relative if relative else None
        if path == self._custom_path:
            return
        self._custom_path = path
        self._custom_strip = QImage(str(path)) if path else QImage()
        if path and self._custom_strip.isNull():
            raise RuntimeError(f"cannot load custom sprite strip: {path}")
