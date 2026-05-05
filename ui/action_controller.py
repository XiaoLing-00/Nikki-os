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


class ActionController:
    def normalize(self, emotion: str, action: str) -> tuple[str, str]:
        return EXPRESSION_MAP.get(emotion, "wink"), action or "motion_idle"
