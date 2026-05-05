from __future__ import annotations


def should_store_memory(memory_update: dict | None) -> bool:
    if not memory_update:
        return False
    key_info = str(memory_update.get("key_info", "")).strip()
    if not key_info:
        return False
    ignored = {"无", "none", "null", "无需更新", "不需要"}
    return key_info.lower() not in ignored
