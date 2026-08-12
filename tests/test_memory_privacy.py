from __future__ import annotations

from memory.long_memory import LongMemory
from memory.memory_trigger import should_store_memory


def test_secrets_and_identifiers_are_never_memorized() -> None:
    for text in (
        "我的密码是 secret123",
        "DASHSCOPE_API_KEY=sk-1234567890abcdef",
        "电话 13800138000",
        "邮箱 user@example.com",
    ):
        assert not should_store_memory({"key_info": text})


def test_memory_crud_deduplication_and_relevance(tmp_path) -> None:
    memory = LongMemory(tmp_path / "memory.sqlite3")
    assert memory.add_memory("晓灵喜欢服装设计", "positive", "dialogue")
    assert not memory.add_memory("晓灵喜欢服装设计", "positive", "dialogue")
    item = memory.list_memories()[0]
    memory.update_memory(item["id"], "晓灵喜欢服装和手工", "positive")
    assert memory.relevant_memories("手工面料")[0]["key_info"] == "晓灵喜欢服装和手工"
    memory.delete_memory(item["id"])
    assert memory.list_memories() == []
