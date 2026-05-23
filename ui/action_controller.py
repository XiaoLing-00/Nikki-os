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
    "motion_idle": "idle",
    "motion_tilt_head": "review",
    "motion_wave": "waving",
    "motion_comfort": "waiting",
    "motion_excited": "jumping",
    "motion_think": "review",
    "motion_listen": "waiting",
    "motion_dragging": "waiting",
    "motion_shy": "waiting",
    "idle": "idle",
    "waiting": "waiting",
    "running": "running",
    "review": "review",
    "failed": "failed",
    "waving": "waving",
    "jumping": "jumping",
    "reading": "reading",
    "thinking": "thinking",
    "encourage": "encourage",
    "comfort": "comfort",
    "shy": "shy",
    "tired": "tired",
    "cheer": "cheer",
    "snack": "snack",
    "designer_work": "designer_work",
}

SCENE_ACTION_MAP = {
    "coding": "thinking",
    "paper_writing": "reading",
    "research": "reading",
    "ppt_defense": "cheer",
    "error_debug": "comfort",
    "video_relax": "snack",
    "game": "waiting",
    "meeting": "idle",
    "idle_long": "waiting",
    "late_night": "tired",
    "chat_social": "idle",
    "file_manage": "review",
    "ai_chat": "thinking",
    "daily_unknown": "idle",
}

CUSTOM_ACTIONS = {
    "reading",
    "thinking",
    "encourage",
    "comfort",
    "shy",
    "tired",
    "cheer",
    "snack",
    "designer_work",
}

EMOTION_ACTION_MAP = {
    "sad": "comfort",
    "cry": "comfort",
    "angry": "failed",
    "punch": "failed",
    "awkward": "waiting",
    "dizzy": "thinking",
    "happy": "jumping",
    "love": "waving",
}

BUSY_ACTIONS = {"running", "review", "thinking", "reading", "designer_work"}
DIRECT_STATES = {
    "idle",
    "waiting",
    "running",
    "review",
    "failed",
    "waving",
    "jumping",
    "running-left",
    "running-right",
    "reading",
    "thinking",
    "encourage",
    "comfort",
    "shy",
    "tired",
    "cheer",
    "snack",
    "designer_work",
}


class ActionController:
    def normalize(self, emotion: str, action: str, context: dict | None = None) -> tuple[str, str]:
        context = context or {}
        expression = EXPRESSION_MAP.get(emotion, "wink")
        decided_action = self.decide_action(emotion, action, context)
        return expression, decided_action

    def decide_action(self, emotion: str, action: str, context: dict | None = None) -> str:
        context = context or {}
        scene_id = str(context.get("scene_id") or (context.get("scene") or {}).get("id") or "")
        current_task = context.get("current_task")

        if scene_id in {"meeting", "game"}:
            return SCENE_ACTION_MAP[scene_id]
        if scene_id == "error_debug":
            return "comfort"
        if emotion in EMOTION_ACTION_MAP:
            return EMOTION_ACTION_MAP[emotion]
        if action in {"idle", "review"} and scene_id in SCENE_ACTION_MAP:
            return SCENE_ACTION_MAP[scene_id]
        if action in DIRECT_STATES:
            return action
        if action in ACTION_MAP:
            mapped = ACTION_MAP[action]
            if current_task and mapped in BUSY_ACTIONS:
                return "running"
            if mapped in {"idle", "review"} and scene_id in SCENE_ACTION_MAP:
                return SCENE_ACTION_MAP[scene_id]
            if mapped in DIRECT_STATES:
                return mapped
            return mapped
        return SCENE_ACTION_MAP.get(scene_id, "idle")
