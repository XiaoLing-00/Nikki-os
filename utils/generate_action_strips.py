from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PET_DIR = ROOT / "assets" / "pets" / "nuannuan"
SPRITESHEET = PET_DIR / "spritesheet.webp"
ACTIONS_DIR = PET_DIR / "actions"
CELL_W = 192
CELL_H = 208


ROWS = {
    "idle": 0,
    "waiting": 6,
    "review": 8,
}


def extract_frames(row: str, count: int = 6) -> list[Image.Image]:
    sheet = Image.open(SPRITESHEET).convert("RGBA")
    y = ROWS[row] * CELL_H
    return [
        sheet.crop((index * CELL_W, y, (index + 1) * CELL_W, y + CELL_H)).convert("RGBA")
        for index in range(count)
    ]


def compose_strip(frames: list[Image.Image]) -> Image.Image:
    strip = Image.new("RGBA", (CELL_W * len(frames), CELL_H), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        strip.alpha_composite(frame, (index * CELL_W, 0))
    return strip


def draw_book(draw: ImageDraw.ImageDraw, frame_index: int) -> None:
    y_shift = 1 if frame_index in {1, 4} else 0
    left = [(48, 134 + y_shift), (92, 126 + y_shift), (94, 166 + y_shift), (47, 174 + y_shift)]
    right = [(94, 126 + y_shift), (139, 134 + y_shift), (141, 174 + y_shift), (95, 166 + y_shift)]
    draw.polygon(left, fill=(255, 244, 222, 255), outline=(164, 102, 122, 255))
    draw.polygon(right, fill=(255, 238, 213, 255), outline=(164, 102, 122, 255))
    draw.line((94, 128 + y_shift, 95, 167 + y_shift), fill=(164, 102, 122, 255), width=2)
    for offset in (10, 20, 30):
        draw.line((58, 142 + y_shift + offset // 5, 84, 138 + y_shift + offset // 5), fill=(218, 159, 171, 255), width=1)
        draw.line((104, 138 + y_shift + offset // 5, 130, 142 + y_shift + offset // 5), fill=(218, 159, 171, 255), width=1)


def draw_thought(draw: ImageDraw.ImageDraw, frame_index: int) -> None:
    alpha = 210 + (frame_index % 2) * 35
    dots = [
        (130, 62, 7),
        (142, 50, 10),
        (158, 38, 14),
    ]
    for x, y, radius in dots:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 238, 247, alpha), outline=(205, 121, 154, 230))


def draw_comfort_heart(draw: ImageDraw.ImageDraw, frame_index: int) -> None:
    y_shift = 1 if frame_index in {2, 3} else 0
    x = 126
    y = 112 + y_shift
    color = (236, 91, 139, 235)
    outline = (158, 74, 106, 230)
    draw.ellipse((x - 13, y - 12, x + 1, y + 2), fill=color, outline=outline)
    draw.ellipse((x - 1, y - 12, x + 13, y + 2), fill=color, outline=outline)
    draw.polygon([(x - 14, y - 4), (x + 14, y - 4), (x, y + 18)], fill=color, outline=outline)


def draw_snack(draw: ImageDraw.ImageDraw, frame_index: int) -> None:
    bag_shift = 1 if frame_index in {1, 4} else 0
    bag = (118, 128 + bag_shift, 153, 175 + bag_shift)
    draw.rounded_rectangle(bag, radius=6, fill=(231, 55, 73, 255), outline=(130, 51, 65, 255), width=2)
    draw.polygon([(120, 130 + bag_shift), (151, 130 + bag_shift), (146, 143 + bag_shift), (124, 142 + bag_shift)], fill=(255, 221, 86, 255))
    draw.ellipse((127, 148 + bag_shift, 145, 164 + bag_shift), fill=(255, 183, 52, 255), outline=(151, 82, 43, 255), width=1)
    draw.ellipse((82, 111 - (frame_index % 2), 98, 121 - (frame_index % 2)), fill=(255, 185, 54, 255), outline=(151, 82, 43, 255), width=1)
    draw.line((86, 116 - (frame_index % 2), 94, 114 - (frame_index % 2)), fill=(221, 94, 55, 255), width=1)


def make_action(name: str, base_row: str, drawer) -> None:
    frames = extract_frames(base_row)
    output_frames = []
    for index, frame in enumerate(frames):
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        drawer(draw, index)
        frame.alpha_composite(overlay)
        output_frames.append(frame)
    compose_strip(output_frames).save(ACTIONS_DIR / f"{name}.webp", "WEBP", lossless=True, quality=100, method=6)


def make_contact_sheet(action_names: list[str]) -> None:
    cell_gap = 8
    sheet = Image.new("RGBA", (CELL_W * 6, (CELL_H + cell_gap) * len(action_names)), (255, 250, 253, 255))
    for row, name in enumerate(action_names):
        strip = Image.open(ACTIONS_DIR / f"{name}.webp").convert("RGBA")
        sheet.alpha_composite(strip, (0, row * (CELL_H + cell_gap)))
    sheet.save(ACTIONS_DIR / "generated-actions-contact-sheet.png")


def main() -> None:
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    make_action("reading", "review", draw_book)
    make_action("thinking", "review", draw_thought)
    make_action("comfort", "waiting", draw_comfort_heart)
    make_action("snack", "idle", draw_snack)
    make_contact_sheet(["reading", "thinking", "comfort", "snack"])


if __name__ == "__main__":
    main()
