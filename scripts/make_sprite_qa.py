from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites" / "nuannuan"
OUTPUT = ROOT / "qa" / "sprites"
STATES = ("talking", "listening", "comfort", "dragging", "angry", "love", "sleeping")
CELL = (192, 208)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    contact = Image.new("RGBA", (CELL[0] * 6, (CELL[1] + 28) * len(STATES)), (245, 245, 245, 255))
    dark_contact = Image.new("RGBA", contact.size, (0, 0, 0, 255))
    report: dict[str, object] = {"ok": True, "states": {}}
    for row, state in enumerate(STATES):
        strip = Image.open(SPRITES / "custom" / f"{state}.png").convert("RGBA")
        frames = [strip.crop((i * CELL[0], 0, (i + 1) * CELL[0], CELL[1])) for i in range(6)]
        alpha_bounds = [frame.getchannel("A").getbbox() for frame in frames]
        deltas = [ImageChops.difference(frames[i - 1], frames[i]).getbbox() is not None for i in range(1, 6)]
        pixel_data = strip.get_flattened_data() if hasattr(strip, "get_flattened_data") else strip.getdata()
        green_spill_pixels = sum(
            1
            for red, green, blue, alpha in pixel_data
            if 8 < alpha < 240 and green > max(red, blue) * 1.05 and green > 40
        )
        ok = (
            strip.size == (CELL[0] * 6, CELL[1])
            and all(alpha_bounds)
            and all(deltas)
            and green_spill_pixels == 0
        )
        report["ok"] = bool(report["ok"]) and ok
        report["states"][state] = {
            "ok": ok,
            "strip_size": list(strip.size),
            "frames": 6,
            "alpha_bounds": alpha_bounds,
            "adjacent_frames_differ": deltas,
            "green_spill_pixels": green_spill_pixels,
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
    (OUTPUT / "custom-qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
