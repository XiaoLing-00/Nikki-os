from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from animation.states import STATE_PRIORITY, AnimationState


class AnimationStateMachine(QObject):
    state_changed = pyqtSignal(object, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.current = AnimationState.IDLE
        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self.force_idle)

    def request(
        self,
        state: AnimationState,
        emotion: str = "wink",
        action: str = "motion_idle",
        duration_ms: int | None = None,
        force: bool = False,
    ) -> bool:
        if not force and STATE_PRIORITY[state] < STATE_PRIORITY[self.current]:
            return False
        self.current = state
        self._return_timer.stop()
        self.state_changed.emit(state, emotion, action)
        if duration_ms and state is not AnimationState.IDLE:
            self._return_timer.start(max(100, duration_ms))
        return True

    def release(self, state: AnimationState) -> None:
        if self.current is state:
            self.force_idle()

    def force_idle(self) -> None:
        self.current = AnimationState.IDLE
        self._return_timer.stop()
        self.state_changed.emit(AnimationState.IDLE, "wink", "motion_idle")
