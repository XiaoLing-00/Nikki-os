from __future__ import annotations

import re

_SENSITIVE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b\d{17}[\dXx]\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?i)(password|passwd|密码|密钥|token|api[_ -]?key)\s*(?:是|[:=])\s*\S+"),
)


def should_store_memory(memory_update: dict | None) -> bool:
    if not memory_update:
        return False
    key_info = str(memory_update.get("key_info", "")).strip()
    if not key_info:
        return False
    ignored = {"无", "none", "null", "无需更新", "不需要"}
    return key_info.lower() not in ignored and not contains_sensitive_information(key_info)


def contains_sensitive_information(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)
