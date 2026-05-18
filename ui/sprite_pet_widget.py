from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QRect, QTimer, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QWidget


CELL_WIDTH = 192
CELL_HEIGHT = 208


@dataclass(frozen=True)
class AnimationSpec:
    row: int
    durations: tuple[int, ...]


ANIMATIONS: dict[str, AnimationSpec] = {
    "idle": AnimationSpec(0, (280, 110, 110, 140, 140, 320)),
    "running-right": AnimationSpec(1, (120, 120, 120, 120, 120, 120, 120, 220)),
    "running-left": AnimationSpec(2, (120, 120, 120, 120, 120, 120, 120, 220)),
    "waving": AnimationSpec(3, (140, 140, 140, 280)),
    "jumping": AnimationSpec(4, (140, 140, 140, 140, 280)),
    "failed": AnimationSpec(5, (140, 140, 140, 140, 140, 140, 140, 240)),
    "waiting": AnimationSpec(6, (150, 150, 150, 150, 150, 260)),
    "running": AnimationSpec(7, (120, 120, 120, 120, 120, 220)),
    "review": AnimationSpec(8, (150, 150, 150, 150, 150, 280)),
}


MOTION_TO_STATE = {
    "motion_idle": "idle",
    "motion_tilt_head": "review",
    "motion_wave": "waving",
    "motion_comfort": "waiting",
    "motion_excited": "jumping",
    "motion_think": "review",
    "motion_listen": "waiting",
    "motion_dragging": "running",
    "motion_shy": "waiting",
}

EXPRESSION_TO_STATE = {
    "cry": "failed",
    "sad": "failed",
    "awkward": "waiting",
    "dizzy": "review",
    "punch": "failed",
    "angry": "failed",
    "love": "waving",
    "happy": "jumping",
}


class SpritePetWidget(QWidget):
    def __init__(self, spritesheet_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spritesheet_path = spritesheet_path
        self.spritesheet = QPixmap(str(spritesheet_path))
        self.state = "idle"
        self.frame_index = 0
        self.pointer_enabled = True

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_frame)
        self.timer.start(self._current_duration())

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_expression(self, expression: str) -> None:
        state = EXPRESSION_TO_STATE.get(expression)
        if state:
            self.set_state(state)

    def play_motion(self, motion: str) -> None:
        self.set_state(MOTION_TO_STATE.get(motion, motion if motion in ANIMATIONS else "idle"))

    def speak(self, expression: str, motion: str) -> None:
        state = MOTION_TO_STATE.get(motion)
        if not state:
            state = EXPRESSION_TO_STATE.get(expression, "idle")
        self.set_state(state)

    def set_pointer_enabled(self, enabled: bool) -> None:
        self.pointer_enabled = enabled

    def refresh_viewport(self) -> None:
        self.update()

    def set_idle_state(self, state: str) -> None:
        if state == "night":
            self.set_state("waiting")
            return
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        if state not in ANIMATIONS:
            state = "idle"
        if state == self.state:
            return
        self.state = state
        self.frame_index = 0
        self.timer.start(self._current_duration())
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.spritesheet.isNull():
            return

        spec = ANIMATIONS[self.state]
        source = QRect(
            self.frame_index * CELL_WIDTH,
            spec.row * CELL_HEIGHT,
            CELL_WIDTH,
            CELL_HEIGHT,
        )

        available = self.rect()
        scale = min(available.width() / CELL_WIDTH, available.height() / CELL_HEIGHT)
        target_width = int(CELL_WIDTH * scale)
        target_height = int(CELL_HEIGHT * scale)
        target = QRect(
            available.x() + (available.width() - target_width) // 2,
            available.y() + available.height() - target_height,
            target_width,
            target_height,
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(target, self.spritesheet, source)

    def _advance_frame(self) -> None:
        spec = ANIMATIONS[self.state]
        self.frame_index = (self.frame_index + 1) % len(spec.durations)
        self.timer.start(self._current_duration())
        self.update()

    def _current_duration(self) -> int:
        spec = ANIMATIONS[self.state]
        return spec.durations[self.frame_index % len(spec.durations)]
