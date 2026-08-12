from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtGui import QImage

from animation.action_mapper import ActionMapper
from animation.states import AnimationState
from renderers.sprite_renderer import SpriteRenderer

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "sprites" / "nuannuan" / "manifest.json"


def test_every_semantic_state_has_sprite_mapping() -> None:
    states = json.loads(MANIFEST.read_text(encoding="utf-8"))["states"]
    assert set(item.value for item in AnimationState) <= set(states)


@pytest.mark.parametrize("state", ["talking", "listening", "comfort", "dragging", "angry", "happy", "sleeping"])
def test_generated_strips_are_valid_rgba_six_frame_assets(state: str) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    path = MANIFEST.parent / manifest["states"][state]["strip"]
    image = QImage(str(path))
    assert not image.isNull()
    assert (image.width(), image.height()) == (192 * 6, 208)
    assert image.hasAlphaChannel()


def test_sprite_renderer_switches_between_atlas_and_custom_strip(qtbot) -> None:
    renderer = SpriteRenderer(MANIFEST)
    qtbot.addWidget(renderer)
    renderer.play_state(AnimationState.TALKING, "wink", "motion_talk")
    assert renderer._custom_path and renderer._custom_path.name == "talking.png"
    assert not renderer._custom_strip.isNull()
    renderer.play_state(AnimationState.IDLE, "wink", "motion_idle")
    assert renderer._custom_path is None


def test_action_mapper_never_leaks_unknown_model_values() -> None:
    mapped = ActionMapper().map("unknown-emotion", "destroy_everything")
    assert mapped.state in set(AnimationState)
    assert mapped.action == "motion_idle"
