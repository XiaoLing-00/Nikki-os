from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from animation.states import AnimationState  # noqa: E402
from renderers.sprite_renderer import SpriteRenderer  # noqa: E402

CELL = (215, 330)
GRID = (5, 3)


def green_dominant_pixels(image: QImage, dominance: int = 3) -> int:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    payload = bytes(rgba.bits().asstring(rgba.sizeInBytes()))
    return sum(
        1
        for index in range(0, len(payload), 4)
        if payload[index + 1] > max(payload[index], payload[index + 2]) + dominance
    )


def render_contact(renderer: SpriteRenderer, background: QColor) -> QImage:
    contact = QImage(
        CELL[0] * GRID[0],
        CELL[1] * GRID[1],
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    contact.fill(background)
    painter = QPainter(contact)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for index, state in enumerate(AnimationState):
        renderer.play_state(state, "wink", "motion_idle")
        renderer._timer.stop()
        renderer._frame = 0
        QApplication.processEvents()
        frame = renderer.render_current_frame(background)
        left = index % GRID[0] * CELL[0]
        top = index // GRID[0] * CELL[1]
        painter.drawImage(left, top, frame)
    painter.end()
    return contact


def main() -> int:
    parser = argparse.ArgumentParser(description="Render every sprite state through the real Qt widget.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "qa" / "sprites")
    parser.add_argument("--label", default=platform.system().lower())
    args = parser.parse_args()
    app = QApplication(["nikki-sprite-runtime-qa"])
    renderer = SpriteRenderer(ROOT / "assets" / "sprites" / "nuannuan" / "manifest.json")
    renderer.resize(*CELL)
    renderer.show()
    QApplication.processEvents()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    images = {
        "dark": render_contact(renderer, QColor(0, 0, 0)),
        "light": render_contact(renderer, QColor(245, 245, 245)),
    }
    counts = {}
    paths = {}
    for theme, image in images.items():
        path = args.output_dir / f"runtime-{args.label}-{theme}.png"
        image.save(str(path))
        try:
            paths[theme] = str(path.resolve().relative_to(ROOT))
        except ValueError:
            paths[theme] = str(path.resolve())
        counts[theme] = green_dominant_pixels(image)
    report = {
        "ok": all(count == 0 for count in counts.values()),
        "platform": platform.platform(),
        "states": [state.value for state in AnimationState],
        "window_size": list(CELL),
        "green_dominant_pixels": counts,
        "images": paths,
    }
    report_path = args.output_dir / f"runtime-{args.label}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    app.quit()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
