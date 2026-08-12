from __future__ import annotations

from dataclasses import dataclass

from animation.states import AnimationState

ALLOWED_EMOTIONS = frozenset(
    {"wink", "love", "cry", "awkward", "dizzy", "rose", "punch", "gentle", "sad", "angry", "happy"}
)
ALLOWED_ACTIONS = frozenset(
    {
        "motion_idle",
        "motion_tilt_head",
        "motion_wave",
        "motion_comfort",
        "motion_excited",
        "motion_think",
        "motion_listen",
        "motion_dragging",
        "motion_shy",
        "motion_talk",
    }
)


@dataclass(frozen=True)
class MappedAction:
    state: AnimationState
    emotion: str
    action: str


class ActionMapper:
    """Convert the model-facing emotion/action contract into renderer-neutral state."""

    _ACTION_STATES = {
        "motion_tilt_head": AnimationState.THINKING,
        "motion_think": AnimationState.THINKING,
        "motion_wave": AnimationState.GREETING,
        "motion_comfort": AnimationState.COMFORT,
        "motion_excited": AnimationState.HAPPY,
        "motion_listen": AnimationState.LISTENING,
        "motion_dragging": AnimationState.DRAGGING,
        "motion_shy": AnimationState.HAPPY,
        "motion_talk": AnimationState.TALKING,
    }
    _EMOTION_STATES = {
        "wink": AnimationState.HAPPY,
        "love": AnimationState.HAPPY,
        "rose": AnimationState.HAPPY,
        "happy": AnimationState.HAPPY,
        "gentle": AnimationState.COMFORT,
        "cry": AnimationState.SAD,
        "sad": AnimationState.SAD,
        "awkward": AnimationState.ERROR,
        "dizzy": AnimationState.ERROR,
        "punch": AnimationState.ANGRY,
        "angry": AnimationState.ANGRY,
    }

    def map(self, emotion: str | None, action: str | None) -> MappedAction:
        safe_emotion = emotion if emotion in ALLOWED_EMOTIONS else "wink"
        safe_action = action if action in ALLOWED_ACTIONS else "motion_idle"
        state = self._ACTION_STATES.get(safe_action)
        if state is None or safe_action == "motion_idle":
            state = self._EMOTION_STATES.get(safe_emotion, AnimationState.TALKING)
        return MappedAction(state, safe_emotion, safe_action)
