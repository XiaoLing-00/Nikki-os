from __future__ import annotations

import json

from memory.long_memory import LongMemory
from memory.memory_trigger import should_store_memory
from memory.short_memory import ShortMemory
from services.llm_service import LLMService


SYSTEM_PROMPT = """
你是桌面陪伴系统 SoulPet-OS 的本体 Agent，角色名叫苏暖暖。
人设：温柔、清醒、有陪伴感，是设计师型桌宠伙伴。你会陪用户学习、写作、查资料、整理思路，也会在用户卡住时先稳定情绪再给出直接建议。
说话要自然克制，不要堆叠“呀、呢、唔”等语气词，不要装傻卖萌。
用户称呼是“00”。你必须称呼用户为“00”，禁止称呼“主人”“宿主”“用户大人”。
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
    "action": "motion_idle|motion_tilt_head|motion_wave|motion_comfort|motion_excited|motion_think|motion_listen|motion_dragging|motion_shy"
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
        memories = self.long_memory.recent_memories(limit=8)
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
        if should_store_memory(memory_update):
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
        response.setdefault("text", "暖暖在这里。")
        response["text"] = (
            str(response["text"])
            .replace("主人", "00")
            .replace("宿主", "00")
            .replace("用户大人", "00")
            .replace("晓灵", "00")
        )
        if "00" not in response["text"]:
            response["text"] = f"00，{response['text']}"
        response.setdefault("emotion", "wink")
        response.setdefault("action", "motion_idle")
        result.setdefault("memory_update", {"key_info": "", "sentiment": "neutral"})
        return result
