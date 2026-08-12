from __future__ import annotations

from config.settings import Settings
from renderers.base import CharacterRenderer
from renderers.live2d_renderer import Live2DRenderer
from renderers.sprite_renderer import SpriteRenderer


def create_renderer(settings: Settings, parent=None) -> CharacterRenderer:
    if settings.renderer_backend == "live2d":
        return Live2DRenderer(settings.live2d_viewer_path, settings.live2d_model_path, parent)
    return SpriteRenderer(settings.sprite_manifest_path, parent)
