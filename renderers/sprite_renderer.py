from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageFilter
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
        self._outline_mode = str(self.manifest.get("outline_mode", "original")).lower()
        self._frame_cache: dict[tuple[str, int, int], QImage] = {}
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

    def set_pointer_enabled(self, enabled: bool) -> None:
        del enabled

    def refresh_viewport(self) -> None:
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
        source_row = 0 if not self._custom_strip.isNull() else int(config.get("row", 0))
        frame = self._render_frame(image, source_row, cell_w, cell_h)
        scale = min(self.width() / cell_w, self.height() / cell_h)
        state_scale = min(1.0, max(0.5, float(config.get("scale", 1.0))))
        target_w = cell_w * scale * state_scale
        target_h = cell_h * scale * state_scale
        bottom_margin = max(0.0, float(config.get("bottom_margin", 0.0))) * scale
        target = QRectF(
            (self.width() - target_w) / 2,
            self.height() - bottom_margin - target_h,
            target_w,
            target_h,
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(target, frame, QRectF(0, 0, cell_w, cell_h))

    def _render_frame(self, image: QImage, row: int, cell_w: int, cell_h: int) -> QImage:
        if self._outline_mode != "soft":
            return image.copy(self._frame * cell_w, row * cell_h, cell_w, cell_h)
        source_id = str(self._custom_path) if self._custom_path else "atlas"
        key = (source_id, row, self._frame)
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached
        frame = image.copy(self._frame * cell_w, row * cell_h, cell_w, cell_h)
        softened = self._soften_outer_outline(frame)
        self._frame_cache[key] = softened
        return softened

    @staticmethod
    def _soften_outer_outline(frame: QImage) -> QImage:
        """Reduce only dark ink touching transparency; preserve interior line art."""
        rgba = frame.convertToFormat(QImage.Format.Format_RGBA8888)
        width, height = rgba.width(), rgba.height()
        payload = bytes(rgba.bits().asstring(rgba.sizeInBytes()))
        image = Image.frombytes("RGBA", (width, height), payload)
        alpha = image.getchannel("A")
        near_edge = alpha.filter(ImageFilter.MinFilter(3))
        edge_band = alpha.filter(ImageFilter.MinFilter(5))
        flatten = lambda layer: (  # noqa: E731 - Pillow 12/13 compatibility shim
            layer.get_flattened_data() if hasattr(layer, "get_flattened_data") else layer.getdata()
        )
        output: list[tuple[int, int, int, int]] = []
        for (red, green, blue, visible_alpha), edge_1, edge_2 in zip(
            flatten(image), flatten(near_edge), flatten(edge_band), strict=True
        ):
            if visible_alpha == 0:
                output.append((0, 0, 0, 0))
                continue
            luminance = (red * 54 + green * 183 + blue * 19) >> 8
            if edge_1 < 224 and luminance < 112:
                strength = 0.78
            elif edge_2 < 224 and luminance < 88:
                strength = 0.38
            else:
                strength = 0.0
            if strength:
                fill_red, fill_green, fill_blue = 116, 66, 82
                red = round(red + (fill_red - red) * strength)
                green = round(green + (fill_green - green) * strength)
                blue = round(blue + (fill_blue - blue) * strength)
            output.append((red, green, blue, visible_alpha))
        softened = Image.new("RGBA", (width, height))
        softened.putdata(output)
        result = QImage(
            softened.tobytes(),
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        )
        return result.copy()

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
