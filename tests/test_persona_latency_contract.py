from __future__ import annotations

from unittest.mock import Mock

from agents.persona_agent import PersonaAgent
from memory.short_memory import ShortMemory


def test_persona_sends_bounded_nonduplicated_history() -> None:
    llm = Mock()
    llm.chat_json.return_value = {
        "context": {},
        "response": {"text": "晓灵，暖暖在这里呀。", "emotion": "wink", "action": "motion_idle"},
        "memory_update": {"key_info": "", "sentiment": "neutral"},
    }
    short_memory = ShortMemory(max_turns=15)
    for index in range(12):
        short_memory.add_user(f"user-{index}")
        short_memory.add_assistant(f"assistant-{index}")
    long_memory = Mock()
    long_memory.relevant_memories.return_value = []
    long_memory.profile.return_value = {"name": "晓灵"}
    long_memory.stats.return_value = {"affection": 1}
    long_memory.recent_interactions.return_value = []
    agent = PersonaAgent(llm, short_memory, long_memory)

    agent.reply("你好", {"app": "Codex"})

    call = llm.chat_json.call_args
    assert len(call.kwargs["history"]) == 8
    assert "short_memory" not in call.args[1]
    long_memory.relevant_memories.assert_called_once_with("你好  Codex", limit=4)
    long_memory.recent_interactions.assert_called_once_with(limit=3)
