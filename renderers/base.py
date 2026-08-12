from __future__ import annotations

from typing import Protocol

from animation.states import AnimationState


class CharacterRenderer(Protocol):
    def play_state(self, state: AnimationState, emotion: str, action: str) -> None:
        raise NotImplementedError

    def set_look_vector(self, x: float, y: float) -> None:
        del x, y

    def refresh_viewport(self) -> None:
        raise NotImplementedError

    def set_pointer_enabled(self, enabled: bool) -> None:
        del enabled
