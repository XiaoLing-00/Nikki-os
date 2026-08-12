from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

CELL_SIZE = (192, 208)


def remove_chroma(image: Image.Image, key=(0, 255, 0), threshold: float = 105) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, _alpha = pixels[x, y]
            distance = ((red - key[0]) ** 2 + (green - key[1]) ** 2 + (blue - key[2]) ** 2) ** 0.5
            if distance <= threshold or (green > red * 1.35 and green > blue * 1.35 and green > 120):
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def remove_neighbor_fragments(slot: Image.Image) -> Image.Image:
    """Drop disconnected character fragments leaking in from adjacent generated panels."""
    alpha = slot.getchannel("A")
    width, height = alpha.size
    visible = bytearray(1 if value else 0 for value in alpha.tobytes())
    seen = bytearray(width * height)
    components: list[list[int]] = []
    for origin, is_visible in enumerate(visible):
        if not is_visible or seen[origin]:
            continue
        stack = [origin]
        seen[origin] = 1
        component: list[int] = []
        while stack:
            point = stack.pop()
            component.append(point)
            x, y = point % width, point // width
            for neighbor in (point - 1, point + 1, point - width, point + width):
                if neighbor < 0 or neighbor >= width * height or seen[neighbor] or not visible[neighbor]:
                    continue
                nx, ny = neighbor % width, neighbor // width
                if abs(nx - x) + abs(ny - y) != 1:
                    continue
                seen[neighbor] = 1
                stack.append(neighbor)
        components.append(component)
    if not components:
        return slot
    largest_component = max(components, key=len)
    keep = bytearray(width * height)
    for component in components:
        xs = [point % width for point in component]
        touches_side = min(xs) <= 1 or max(xs) >= width - 2
        if not touches_side or component is largest_component:
            for point in component:
                keep[point] = 1
    pixels = slot.load()
    for point, retain in enumerate(keep):
        if not retain:
            x, y = point % width, point // width
            pixels[x, y] = (0, 0, 0, 0)
    return slot


def process(source: Path, output_strip: Path, frames_dir: Path, frame_count: int) -> dict:
    image = Image.open(source).convert("RGB")
    keyed = remove_chroma(image)
    alpha = keyed.getchannel("A")
    raw = alpha.tobytes()
    occupied = [any(raw[y * alpha.width + x] for y in range(alpha.height)) for x in range(alpha.width)]
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x, visible in enumerate(occupied + [False]):
        if visible and start is None:
            start = x
        elif not visible and start is not None:
            if x - start >= 8:
                runs.append((start, x))
            start = None
    if len(runs) != frame_count:
        runs = [
            (round(index * image.width / frame_count), round((index + 1) * image.width / frame_count))
            for index in range(frame_count)
        ]
    cells: list[Image.Image] = []
    report: list[dict] = []
    for index in range(frame_count):
        left, right = runs[index]
        slot = keyed.crop((left, 0, right, image.height))
        slot = remove_neighbor_fragments(slot)
        # Generative six-panel sheets can overlap a few pixels across seams.
        # Clear the seam guard band deterministically before fitting the frame.
        guard = max(2, round(slot.width * 0.07))
        pixels = slot.load()
        for y in range(slot.height):
            for x in list(range(guard)) + list(range(slot.width - guard, slot.width)):
                pixels[x, y] = (0, 0, 0, 0)
        bbox = slot.getchannel("A").getbbox()
        if not bbox:
            raise RuntimeError(f"frame {index} is empty")
        sprite = slot.crop(bbox)
        scale = min(182 / sprite.width, 198 / sprite.height)
        size = (max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale)))
        sprite = sprite.resize(size, Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
        x = (CELL_SIZE[0] - sprite.width) // 2
        y = CELL_SIZE[1] - 5 - sprite.height
        cell.alpha_composite(sprite, (x, y))
        cells.append(cell)
        report.append({"frame": index, "source_bbox": bbox, "size": size, "target": [x, y]})

    frames_dir.mkdir(parents=True, exist_ok=True)
    for index, cell in enumerate(cells):
        cell.save(frames_dir / f"{index:02d}.png")
    strip = Image.new("RGBA", (CELL_SIZE[0] * frame_count, CELL_SIZE[1]), (0, 0, 0, 0))
    for index, cell in enumerate(cells):
        strip.alpha_composite(cell, (CELL_SIZE[0] * index, 0))
    output_strip.parent.mkdir(parents=True, exist_ok=True)
    strip.save(output_strip)
    return {"ok": True, "source": str(source), "output": str(output_strip), "frames": report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-strip", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--frame-count", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = process(args.source, args.output_strip, args.frames_dir, args.frame_count)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
