from __future__ import annotations


EXPRESSION_MAP = {
    "gentle": "wink",
    "sad": "cry",
    "angry": "punch",
    "happy": "love",
    "wink": "wink",
    "love": "love",
    "cry": "cry",
    "awkward": "awkward",
    "dizzy": "dizzy",
    "rose": "rose",
    "punch": "punch",
}

ACTION_MAP = {
    "motion_idle": "motion_idle",
    "motion_tilt_head": "motion_tilt_head",
    "motion_wave": "motion_wave",
    "motion_comfort": "motion_comfort",
    "motion_excited": "motion_excited",
    "motion_think": "motion_think",
    "motion_listen": "motion_listen",
    "motion_dragging": "motion_dragging",
    "motion_shy": "motion_shy",
    "idle": "idle",
    "waiting": "waiting",
    "running": "running",
    "review": "review",
    "failed": "failed",
    "waving": "waving",
    "jumping": "jumping",
}


class ActionController:
    def normalize(self, emotion: str, action: str) -> tuple[str, str]:
        return EXPRESSION_MAP.get(emotion, "wink"), ACTION_MAP.get(action, "motion_idle")
