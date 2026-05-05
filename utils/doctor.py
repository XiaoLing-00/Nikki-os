from __future__ import annotations

import json
from pathlib import Path

import requests
from PyQt6.QtGui import QImage

from config.settings import BASE_DIR, Settings


def run_doctor(settings: Settings, check_api: bool = False) -> int:
    checks: list[tuple[str, bool, str]] = []
    env_file = BASE_DIR / ".env"
    loose_env_file = BASE_DIR / "env"

    checks.append(("env file", bool(settings.env_file_path), _env_message(settings.env_file_path)))
    if loose_env_file.exists() and not env_file.exists():
        checks.append(
            ("env filename hint",
             False,
             "发现文件名是 env；当前已兼容读取，但建议重命名为 .env，避免部署时混淆。"),
        )
    checks.append(
        ("DASHSCOPE_API_KEY",
         bool(settings.dashscope_api_key),
         f"loaded length={len(settings.dashscope_api_key or '')}"),
    )
    checks.append(("text model", bool(settings.text_model), settings.text_model))
    checks.append(("vision model", bool(settings.vision_model), settings.vision_model))
    checks.append(("asr model", bool(settings.asr_model), settings.asr_model))

    checks.extend(_check_live2d_assets(settings.live2d_model_path))
    if check_api:
        checks.append(("DashScope ping", *_ping_dashscope(settings)))

    print("SoulPet-OS Doctor")
    print("=" * 48)
    for name, ok, detail in checks:
        status = "OK" if ok else "WARN"
        print(f"[{status}] {name}: {detail}")
    return 0 if all(ok for name, ok, _detail in checks if name != "env filename hint") else 1


def _env_message(path: Path | None) -> str:
    if path:
        return str(path)
    return "未找到 .env 或 env；请在项目根目录配置 DASHSCOPE_API_KEY。"


def _check_live2d_assets(model_path: Path) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    root = model_path.parent
    if not model_path.exists():
        return [("Live2D model3.json", False, f"missing: {model_path}")]

    try:
        model = json.loads(model_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [("Live2D model3.json", False, f"invalid JSON: {exc}")]

    refs = model.get("FileReferences", {})
    files: list[str] = []
    if refs.get("Moc"):
        files.append(refs["Moc"])
    if refs.get("Physics"):
        files.append(refs["Physics"])
    files.extend(refs.get("Textures", []))
    for motions in refs.get("Motions", {}).values():
        files.extend(item.get("File", "") for item in motions)
    files.extend(item.get("File", "") for item in refs.get("Expressions", []))

    missing = [item for item in files if item and not (root / item).exists()]
    checks.append(("Live2D file references", not missing, "missing=" + ", ".join(missing) if missing else "all referenced files exist"))

    textures = refs.get("Textures", [])
    checks.append(("Live2D texture count", len(textures) >= 2, f"{len(textures)} texture(s): {', '.join(textures)}"))
    for texture in textures:
        image_path = root / texture
        image = QImage(str(image_path))
        checks.append(
            (f"texture {Path(texture).name}",
             not image.isNull(),
             f"{image.width()}x{image.height()} alpha={image.hasAlphaChannel()} bytes={image_path.stat().st_size if image_path.exists() else 0}"),
        )

    expressions = [item.get("Name", "") for item in refs.get("Expressions", [])]
    expected = {"awkward", "cry", "dizzy", "love", "punch", "rose", "wink"}
    missing_expr = sorted(expected.difference(expressions))
    checks.append(("Live2D expressions", not missing_expr, "names=" + ", ".join(expressions)))
    return checks


def _ping_dashscope(settings: Settings) -> tuple[bool, str]:
    if not settings.dashscope_api_key:
        return False, "skip: DASHSCOPE_API_KEY not loaded"
    try:
        response = requests.post(
            f"{settings.dashscope_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.text_model,
                "messages": [{"role": "user", "content": "只回复 OK"}],
                "temperature": 0,
                "max_tokens": 8,
            },
            timeout=15,
        )
        if response.ok:
            return True, f"{response.status_code}: {response.json()['choices'][0]['message']['content'][:20]}"
        return False, f"{response.status_code}: {response.text[:200]}"
    except Exception as exc:
        return False, str(exc)
