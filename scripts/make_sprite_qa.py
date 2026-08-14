from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites" / "nuannuan"
OUTPUT = ROOT / "qa" / "sprites"
STATES = ("talking", "listening", "comfort", "dragging", "angry", "love", "sleeping", "error")
CELL = (192, 208)


def flattened(image: Image.Image):
    return image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()


def edge_green_pixels(image: Image.Image, radius: int = 3) -> list[tuple[int, int]]:
    alpha = image.getchannel("A")
    interior = alpha.filter(ImageFilter.MinFilter(radius * 2 + 1))
    result = []
    for index, (pixel, minimum_alpha) in enumerate(
        zip(flattened(image), flattened(interior), strict=True)
    ):
        red, green, blue, visible_alpha = pixel
        if visible_alpha > 0 and minimum_alpha < 255 and green > max(red, blue) + 3:
            result.append((index % image.width, index // image.width))
    return result


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    contact = Image.new("RGBA", (CELL[0] * 6, (CELL[1] + 28) * len(STATES)), (245, 245, 245, 255))
    dark_contact = Image.new("RGBA", contact.size, (0, 0, 0, 255))
    atlas = Image.open(SPRITES / "spritesheet.webp").convert("RGBA")
    atlas_frames = [
        atlas.crop((column * CELL[0], row * CELL[1], (column + 1) * CELL[0], (row + 1) * CELL[1]))
        for row in range(9)
        for column in range(8)
    ]
    atlas_boundary_green = len(edge_green_pixels(atlas))
    atlas_scaled_boundary_green = sum(
        len(
            edge_green_pixels(
                frame.resize((CELL[0] * 2, CELL[1] * 2), Image.Resampling.BILINEAR),
                radius=4,
            )
        )
        for frame in atlas_frames
    )
    atlas_ok = (
        atlas.size == (CELL[0] * 8, CELL[1] * 9)
        and atlas_boundary_green == 0
        and atlas_scaled_boundary_green == 0
    )
    report: dict[str, object] = {
        "ok": atlas_ok,
        "atlas": {
            "ok": atlas_ok,
            "size": list(atlas.size),
            "cells": len(atlas_frames),
            "boundary_green_spill_pixels": atlas_boundary_green,
            "scaled_boundary_green_spill_pixels": atlas_scaled_boundary_green,
        },
        "states": {},
    }
    for row, state in enumerate(STATES):
        strip = Image.open(SPRITES / "custom" / f"{state}.png").convert("RGBA")
        frames = [strip.crop((i * CELL[0], 0, (i + 1) * CELL[0], CELL[1])) for i in range(6)]
        alpha_bounds = [frame.getchannel("A").getbbox() for frame in frames]
        deltas = [ImageChops.difference(frames[i - 1], frames[i]).getbbox() is not None for i in range(1, 6)]
        pixel_data = strip.get_flattened_data() if hasattr(strip, "get_flattened_data") else strip.getdata()
        translucent_green_spill_pixels = sum(
            1
            for red, green, blue, alpha in pixel_data
            if 8 < alpha < 240 and green > max(red, blue) * 1.05 and green > 40
        )
        boundary_green_spill_pixels = len(edge_green_pixels(strip))
        scaled_frames = [
            frame.resize((CELL[0] * 2, CELL[1] * 2), Image.Resampling.BILINEAR)
            for frame in frames
        ]
        scaled_boundary_green_spill_pixels = sum(
            len(edge_green_pixels(frame, radius=4)) for frame in scaled_frames
        )
        ok = (
            strip.size == (CELL[0] * 6, CELL[1])
            and all(alpha_bounds)
            and all(deltas)
            and translucent_green_spill_pixels == 0
            and boundary_green_spill_pixels == 0
            and scaled_boundary_green_spill_pixels == 0
        )
        report["ok"] = bool(report["ok"]) and ok
        report["states"][state] = {
            "ok": ok,
            "strip_size": list(strip.size),
            "frames": 6,
            "alpha_bounds": alpha_bounds,
            "adjacent_frames_differ": deltas,
            "green_spill_pixels": translucent_green_spill_pixels,
            "boundary_green_spill_pixels": boundary_green_spill_pixels,
            "scaled_boundary_green_spill_pixels": scaled_boundary_green_spill_pixels,
        }
        y = row * (CELL[1] + 28)
        contact.alpha_composite(strip, (0, y + 28))
        dark_contact.alpha_composite(strip, (0, y + 28))
        ImageDraw.Draw(contact).text((8, y + 6), state, fill=(40, 40, 40, 255))
        ImageDraw.Draw(dark_contact).text((8, y + 6), state, fill=(255, 255, 255, 255))
        frames[0].save(
            OUTPUT / f"{state}-preview.gif",
            save_all=True,
            append_images=frames[1:],
            duration=125,
            loop=0,
            disposal=2,
            transparency=0,
        )
    contact.save(OUTPUT / "custom-contact-sheet.png")
    dark_contact.save(OUTPUT / "custom-contact-sheet-dark.png")
    atlas_preview = atlas.resize((CELL[0] * 4, CELL[1] * 9 // 2), Image.Resampling.LANCZOS)
    atlas_dark = Image.new("RGBA", atlas_preview.size, (0, 0, 0, 255))
    atlas_light = Image.new("RGBA", atlas_preview.size, (245, 245, 245, 255))
    atlas_dark.alpha_composite(atlas_preview)
    atlas_light.alpha_composite(atlas_preview)
    atlas_dark.save(OUTPUT / "atlas-contact-dark.png")
    atlas_light.save(OUTPUT / "atlas-contact-light.png")
    (OUTPUT / "custom-qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
