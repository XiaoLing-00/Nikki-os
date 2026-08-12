from __future__ import annotations

from pathlib import Path

from animation.states import AnimationState
from ui.live2d_widget import Live2DWidget

STATE_FALLBACK = {
    AnimationState.IDLE: ("wink", "motion_idle"),
    AnimationState.TALKING: ("wink", "motion_talk"),
    AnimationState.THINKING: ("dizzy", "motion_think"),
    AnimationState.LISTENING: ("rose", "motion_listen"),
    AnimationState.GREETING: ("wink", "motion_wave"),
    AnimationState.HAPPY: ("love", "motion_excited"),
    AnimationState.COMFORT: ("wink", "motion_comfort"),
    AnimationState.SAD: ("cry", "motion_comfort"),
    AnimationState.ERROR: ("awkward", "motion_idle"),
    AnimationState.ANGRY: ("punch", "motion_excited"),
    AnimationState.VISUAL_REVIEW: ("dizzy", "motion_tilt_head"),
    AnimationState.ROAM_LEFT: ("wink", "motion_idle"),
    AnimationState.ROAM_RIGHT: ("wink", "motion_idle"),
    AnimationState.DRAGGING: ("awkward", "motion_dragging"),
    AnimationState.SLEEPING: ("wink", "motion_idle"),
}


class Live2DRenderer(Live2DWidget):
    def __init__(self, viewer_path: Path, model_path: Path, parent=None) -> None:
        super().__init__(viewer_path, model_path, parent)

    def play_state(self, state: AnimationState, emotion: str, action: str) -> None:
        fallback_emotion, fallback_action = STATE_FALLBACK[state]
        selected_action = action
        if not selected_action or (selected_action == "motion_idle" and state is not AnimationState.IDLE):
            selected_action = fallback_action
        self.speak(emotion or fallback_emotion, selected_action)

    def set_look_vector(self, x: float, y: float) -> None:
        self._run_js(f"window.SoulPet && window.SoulPet.setLookVector({float(x)}, {float(y)});")
