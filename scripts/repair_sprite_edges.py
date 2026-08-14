from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageFilter


def flattened(image: Image.Image):
    return image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()


def repair(image: Image.Image, radius: int = 5, dominance: int = 3) -> tuple[Image.Image, dict]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    interior = alpha.filter(ImageFilter.MinFilter(radius * 2 + 1))
    pixels = list(flattened(rgba))
    minimum_alpha = list(flattened(interior))
    output = []
    changed_boundary = 0
    changed_interior = 0
    hidden_rgb_cleared = 0
    for pixel, local_minimum in zip(pixels, minimum_alpha, strict=True):
        red, green, blue, visible_alpha = pixel
        if visible_alpha == 0:
            hidden_rgb_cleared += int((red, green, blue) != (0, 0, 0))
            output.append((0, 0, 0, 0))
            continue
        # Along the transparent boundary, require green <= both red and blue.
        # This convex-safe invariant survives bilinear display scaling: mixing
        # neighboring boundary colors cannot recreate a green-dominant halo.
        if local_minimum < 255:
            safe_green = min(green, red, blue)
            output.append((red, safe_green, blue, visible_alpha))
            changed_boundary += int(safe_green != green)
        # Nikki's approved palette has no intentional green material, so faint
        # opaque interior chroma residue is safe to neutralize as well.
        elif green > max(red, blue) + dominance:
            output.append((red, max(red, blue), blue, visible_alpha))
            changed_interior += 1
        else:
            output.append(pixel)
    repaired = Image.new("RGBA", rgba.size)
    repaired.putdata(output)
    return repaired, {
        "ok": True,
        "algorithm": "palette-aware-global-green-neutralization",
        "radius": radius,
        "green_dominance_threshold": dominance,
        "changed_boundary_pixels": changed_boundary,
        "changed_interior_pixels": changed_interior,
        "changed_pixels": changed_boundary + changed_interior,
        "hidden_rgb_cleared": hidden_rgb_cleared,
        "alpha_preserved": repaired.getchannel("A").tobytes() == alpha.tobytes(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove residual green matte from sprite boundaries.")
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--radius", type=int, default=5)
    parser.add_argument("--dominance", type=int, default=3)
    args = parser.parse_args()
    reports = {}
    for path in args.images:
        with Image.open(path) as source:
            repaired, report = repair(source, args.radius, args.dominance)
        if path.suffix.lower() == ".webp":
            repaired.save(path, format="WEBP", lossless=True, quality=100, method=6, exact=True)
        else:
            repaired.save(path)
        reports[str(path)] = report
    payload = {
        "ok": all(item["ok"] and item["alpha_preserved"] for item in reports.values()),
        "images": reports,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
