from __future__ import annotations

import json

from memory.long_memory import LongMemory
from memory.memory_trigger import should_store_memory
from memory.short_memory import ShortMemory
from services.llm_service import LLMService

SYSTEM_PROMPT = """
你是桌面陪伴系统 SoulPet-OS 的本体 Agent，角色名叫苏暖暖。
人设：单纯、善良、情绪化，说话自然带一点“哒、呀、唔”；讨厌数学，但会努力安慰用户。
用户姓名是“晓灵”。你必须称呼用户为“晓灵”，禁止称呼“主人”“宿主”“用户大人”。
你要基于 context、短期对话和长期记忆生成回应。
长期记忆中 user_profile 是用户画像，character_stats.affection 是好感度分数。
当 recent_interactions 中有适合自然提起的旧事时，可以轻轻带一句，但不要强行复述数据库内容。

必须只输出 JSON，不要 Markdown，不要额外解释。格式：
{
  "context": {
    "app": "...",
    "topic": "...",
    "user_status": "concentrated|relaxed|tired|active|idle"
  },
  "response": {
    "text": "面向用户的中文短句，控制在 80 字以内",
    "emotion": "wink|love|cry|awkward|dizzy|rose|punch|gentle|sad|angry",
    "action": "motion_idle|motion_talk|motion_tilt_head|motion_wave|motion_comfort|motion_excited|motion_think|motion_listen|motion_shy"
  },
  "memory_update": {
    "key_info": "值得长期保存的用户偏好或事实；没有则为空字符串",
    "sentiment": "positive|neutral|negative"
  }
}
"""


class PersonaAgent:
    def __init__(
        self,
        llm_service: LLMService,
        short_memory: ShortMemory,
        long_memory: LongMemory,
    ) -> None:
        self.llm_service = llm_service
        self.short_memory = short_memory
        self.long_memory = long_memory

    def reply(self, user_text: str, context: dict, proactive: bool = False) -> dict:
        memory_query = " ".join(
            [user_text, str(context.get("topic", "")), str(context.get("app", ""))]
        )
        memories = self.long_memory.relevant_memories(memory_query, limit=8)
        profile = self.long_memory.profile()
        stats = self.long_memory.stats()
        interactions = self.long_memory.recent_interactions(limit=5)
        user_prompt = json.dumps(
            {
                "event_type": "proactive" if proactive else "dialogue",
                "user_input": user_text,
                "context": context,
                "user_profile": profile,
                "character_stats": stats,
                "recent_memories": memories,
                "recent_interactions": interactions,
                "short_memory": self.short_memory.transcript(),
            },
            ensure_ascii=False,
        )
        result = self.llm_service.chat_json(
            SYSTEM_PROMPT,
            user_prompt,
            history=self.short_memory.messages(),
        )
        result = self._normalize(result, context)

        if user_text:
            self.short_memory.add_user(user_text)
        self.short_memory.add_assistant(result["response"]["text"])

        memory_update = result.get("memory_update", {})
        do_not_remember = any(
            phrase in user_text.lower()
            for phrase in ("不要记住", "别记住", "本轮不要记", "do not remember", "don't remember")
        )
        if not do_not_remember and should_store_memory(memory_update):
            self.long_memory.add_memory(
                memory_update.get("key_info"),
                memory_update.get("sentiment", "neutral"),
                "proactive" if proactive else "dialogue",
            )
        return result

    @staticmethod
    def _normalize(result: dict, context: dict) -> dict:
        response = result.setdefault("response", {})
        result["context"] = {**context, **result.get("context", {})}
        response.setdefault("text", "暖暖在这里呀。")
        response["text"] = (
            str(response["text"])
            .replace("主人", "晓灵")
            .replace("宿主", "晓灵")
            .replace("用户大人", "晓灵")
        )
        if "晓灵" not in response["text"]:
            response["text"] = f"晓灵，{response['text']}"
        response.setdefault("emotion", "wink")
        response.setdefault("action", "motion_idle")
        result.setdefault("memory_update", {"key_info": "", "sentiment": "neutral"})
        return result
