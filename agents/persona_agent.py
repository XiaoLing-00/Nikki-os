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
记忆策略：任务进度优先写入 task_update；当天情绪和当前专注内容写入 daily_update；稳定偏好、长期目标和反复出现的习惯才写入 memory_update。普通长期候选会在系统内重复 3 次后升级。

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
    "action": "motion_idle|motion_tilt_head|motion_wave|motion_comfort|motion_excited|motion_think|motion_listen|motion_shy|idle|waiting|reading|thinking|encourage|comfort|shy|tired|cheer|snack|designer_work"
  },
  "memory_update": {
    "key_info": "值得长期保存的用户偏好或事实；没有则为空字符串",
    "sentiment": "positive|neutral|negative"
  },
  "task_update": {
    "title": "任务名；没有则为空字符串",
    "project": "所属项目；没有则为空字符串",
    "chapter": "章节或阶段；没有则为空字符串",
    "subtask": "当前做到哪一步；没有则为空字符串",
    "priority": "urgent|high|normal|low",
    "status": "todo|in_progress|blocked|done"
  },
  "daily_update": {
    "key": "当天状态键，如 current_focus 或 mood；没有则为空字符串",
    "value": "当天状态值；没有则为空字符串"
  },
  "emotion_update": {
    "label": "可沉淀的情绪倾向，如 最近焦虑 或 喜欢温柔直接的提醒；没有则为空字符串",
    "intensity": 0.1
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
        active_tasks = self.long_memory.active_tasks(limit=5)
        today_state = self.long_memory.today_state()
        emotional_patterns = self.long_memory.emotional_patterns(limit=5)
        user_prompt = json.dumps(
            {
                "event_type": "proactive" if proactive else "dialogue",
                "user_input": user_text,
                "context": context,
                "user_profile": profile,
                "character_stats": stats,
                "recent_memories": memories,
                "recent_interactions": interactions,
                "active_tasks": active_tasks,
                "today_state": today_state,
                "emotional_patterns": emotional_patterns,
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
                require_repetition=True,
            )
        source = "proactive" if proactive else "dialogue"
        task_update = result.get("task_update", {})
        if task_update.get("title"):
            self.long_memory.upsert_task(
                task_update.get("title"),
                project=task_update.get("project", ""),
                chapter=task_update.get("chapter", ""),
                subtask=task_update.get("subtask", ""),
                priority=task_update.get("priority", "normal"),
                status=task_update.get("status", "in_progress"),
                source=source,
            )
        daily_update = result.get("daily_update", {})
        if daily_update.get("key") and daily_update.get("value"):
            self.long_memory.add_daily_state(
                daily_update.get("key"),
                daily_update.get("value"),
                source=source,
            )
        emotion_update = result.get("emotion_update", {})
        if emotion_update.get("label"):
            self.long_memory.add_emotional_pattern(
                emotion_update.get("label"),
                intensity=emotion_update.get("intensity", 1.0),
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
        result.setdefault(
            "task_update",
            {
                "title": "",
                "project": "",
                "chapter": "",
                "subtask": "",
                "priority": "normal",
                "status": "in_progress",
            },
        )
        result.setdefault("daily_update", {"key": "", "value": ""})
        result.setdefault("emotion_update", {"label": "", "intensity": 1.0})
        return result
