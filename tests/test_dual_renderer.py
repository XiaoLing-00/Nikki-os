from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from PyQt6.QtGui import QColor, QImage

from animation.action_mapper import ActionMapper
from animation.states import AnimationState
from renderers.sprite_renderer import SpriteRenderer
from scripts.process_custom_strip import process

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "sprites" / "nuannuan" / "manifest.json"


def test_every_semantic_state_has_sprite_mapping() -> None:
    states = json.loads(MANIFEST.read_text(encoding="utf-8"))["states"]
    assert set(item.value for item in AnimationState) <= set(states)


@pytest.mark.parametrize(
    "state",
    ["talking", "listening", "comfort", "dragging", "angry", "happy", "sleeping", "error"],
)
def test_generated_strips_are_valid_rgba_six_frame_assets(state: str) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    path = MANIFEST.parent / manifest["states"][state]["strip"]
    image = QImage(str(path))
    assert not image.isNull()
    assert (image.width(), image.height()) == (192 * 6, 208)
    assert image.hasAlphaChannel()


def test_error_and_sad_use_distinct_animation_assets() -> None:
    states = json.loads(MANIFEST.read_text(encoding="utf-8"))["states"]
    assert states["error"].get("strip")
    assert states["error"] != states["sad"]


def test_sprite_qa_rejects_translucent_opaque_and_scaled_green_edges() -> None:
    report = json.loads((ROOT / "qa/sprites/custom-qa.json").read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["atlas"]["boundary_green_spill_pixels"] == 0
    assert report["atlas"]["scaled_boundary_green_spill_pixels"] == 0
    for state in report["states"].values():
        assert state["green_spill_pixels"] == 0
        assert state["boundary_green_spill_pixels"] == 0
        assert state["scaled_boundary_green_spill_pixels"] == 0


def test_sprite_renderer_switches_between_atlas_and_custom_strip(qtbot) -> None:
    renderer = SpriteRenderer(MANIFEST)
    qtbot.addWidget(renderer)
    renderer.play_state(AnimationState.TALKING, "wink", "motion_talk")
    assert renderer._custom_path and renderer._custom_path.name == "talking.png"
    assert not renderer._custom_strip.isNull()
    renderer.play_state(AnimationState.IDLE, "wink", "motion_idle")
    assert renderer._custom_path is None


def test_sprite_renderer_implements_drag_compatibility_api(qtbot) -> None:
    renderer = SpriteRenderer(MANIFEST)
    qtbot.addWidget(renderer)

    renderer.set_pointer_enabled(False)
    renderer.refresh_viewport()
    renderer.set_pointer_enabled(True)


def test_sprite_renderer_can_render_without_native_window_grab(qtbot) -> None:
    renderer = SpriteRenderer(MANIFEST)
    qtbot.addWidget(renderer)
    renderer.resize(215, 330)
    renderer.play_state(AnimationState.HAPPY, "love", "motion_excited")
    renderer._timer.stop()

    frame = renderer.render_current_frame(QColor(245, 245, 245))

    assert not frame.isNull()
    assert (frame.width(), frame.height()) == (215, 330)
    assert frame.pixelColor(0, 0) == QColor(245, 245, 245)


def test_soft_outline_only_reduces_dark_transparent_boundary() -> None:
    source = QImage(9, 9, QImage.Format.Format_RGBA8888)
    source.fill(QColor(0, 0, 0, 0))
    for y in range(2, 7):
        for x in range(2, 7):
            source.setPixelColor(x, y, QColor(42, 30, 38, 255))
    for y in range(3, 6):
        for x in range(3, 6):
            source.setPixelColor(x, y, QColor(246, 150, 170, 255))
    source.setPixelColor(4, 4, QColor(42, 30, 38, 255))

    result = SpriteRenderer._soften_outer_outline(source)

    assert result.pixelColor(2, 2).lightness() > source.pixelColor(2, 2).lightness()
    assert result.pixelColor(2, 2).alpha() == 255
    assert result.pixelColor(4, 4) == QColor(42, 30, 38, 255)
    assert result.pixelColor(0, 0) == QColor(0, 0, 0, 0)


def test_dragging_state_has_extra_safe_area(qtbot) -> None:
    renderer = SpriteRenderer(MANIFEST)
    qtbot.addWidget(renderer)
    renderer.resize(215, 330)
    renderer.play_state(AnimationState.DRAGGING, "awkward", "motion_dragging")
    renderer._timer.stop()

    frame = renderer.render_current_frame()
    alpha = frame.createAlphaMask()
    occupied = [
        (x, y)
        for y in range(frame.height())
        for x in range(frame.width())
        if alpha.pixelIndex(x, y)
    ]

    assert occupied
    assert min(x for x, _ in occupied) >= 16
    assert max(x for x, _ in occupied) <= frame.width() - 17
    assert min(y for _, y in occupied) >= 7
    assert max(y for _, y in occupied) <= frame.height() - 8


def test_separated_custom_strip_does_not_cut_silhouette_edges(tmp_path) -> None:
    source = Image.new("RGB", (120, 40), (0, 255, 0))
    pixels = source.load()
    for left, right in ((5, 35), (45, 75), (85, 115)):
        for y in range(5, 35):
            for x in range(left, right):
                pixels[x, y] = (255, 120, 160)
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "strip.png"
    source.save(source_path)

    report = process(source_path, output_path, tmp_path / "frames", 3)

    assert all(frame["segmentation"] == "separated-run" for frame in report["frames"])
    assert all(frame["seam_guard_px"] == 0 for frame in report["frames"])
    assert all(frame["source_bbox"] == (0, 5, 30, 35) for frame in report["frames"])


def test_action_mapper_never_leaks_unknown_model_values() -> None:
    mapped = ActionMapper().map("unknown-emotion", "destroy_everything")
    assert mapped.state in set(AnimationState)
    assert mapped.action == "motion_idle"
