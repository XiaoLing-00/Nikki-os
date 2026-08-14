from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class ShortMemory:
    max_turns: int = 15
    _messages: deque[dict[str, str]] = field(init=False)

    def __post_init__(self) -> None:
        self._messages = deque(maxlen=self.max_turns * 2)

    def add(self, role: str, content: str) -> None:
        if content:
            self._messages.append({"role": role, "content": content})

    def add_user(self, content: str) -> None:
        self.add("user", content)

    def add_assistant(self, content: str) -> None:
        self.add("assistant", content)

    def messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def transcript(self, limit: int = 8) -> str:
        pairs = list(self._messages)[-limit:]
        return "\n".join(f"{item['role']}: {item['content']}" for item in pairs)
