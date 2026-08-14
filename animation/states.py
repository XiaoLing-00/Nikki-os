from __future__ import annotations

from enum import Enum


class AnimationState(str, Enum):
    IDLE = "idle"
    TALKING = "talking"
    THINKING = "thinking"
    LISTENING = "listening"
    GREETING = "greeting"
    HAPPY = "happy"
    COMFORT = "comfort"
    SAD = "sad"
    ERROR = "error"
    ANGRY = "angry"
    VISUAL_REVIEW = "visual_review"
    ROAM_LEFT = "roam_left"
    ROAM_RIGHT = "roam_right"
    DRAGGING = "dragging"
    SLEEPING = "sleeping"


STATE_PRIORITY: dict[AnimationState, int] = {
    AnimationState.IDLE: 0,
    AnimationState.ROAM_LEFT: 10,
    AnimationState.ROAM_RIGHT: 10,
    AnimationState.GREETING: 20,
    AnimationState.HAPPY: 20,
    AnimationState.COMFORT: 20,
    AnimationState.SAD: 20,
    AnimationState.ERROR: 20,
    AnimationState.ANGRY: 20,
    AnimationState.VISUAL_REVIEW: 25,
    AnimationState.TALKING: 30,
    AnimationState.THINKING: 40,
    AnimationState.LISTENING: 50,
    AnimationState.DRAGGING: 60,
    AnimationState.SLEEPING: 5,
}
