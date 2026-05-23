from __future__ import annotations

import json
from pathlib import Path

import requests
from PyQt6.QtGui import QImage

from config.settings import BASE_DIR, Settings
from ui.sprite_pet_widget import CELL_HEIGHT, CELL_WIDTH


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

    checks.extend(
        _check_pet_assets(
            settings.pet_manifest_path,
            settings.pet_spritesheet_path,
            settings.pet_actions_path,
        )
    )
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


def _check_pet_assets(
    manifest_path: Path,
    spritesheet_path: Path,
    actions_path: Path,
) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    if not manifest_path.exists():
        return [("Pet manifest", False, f"missing: {manifest_path}")]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [("Pet manifest", False, f"invalid JSON: {exc}")]

    checks.append(("Pet manifest", manifest.get("id") == "nuannuan", f"id={manifest.get('id', '')}"))

    image = QImage(str(spritesheet_path))
    expected_size = (CELL_WIDTH * 8, CELL_HEIGHT * 9)
    actual_size = (image.width(), image.height())
    checks.append(
        (
            "Pet spritesheet",
            not image.isNull() and actual_size == expected_size,
            f"{actual_size[0]}x{actual_size[1]} expected={expected_size[0]}x{expected_size[1]}",
        )
    )

    if not actions_path.exists():
        checks.append(("Pet action manifest", False, f"missing: {actions_path}"))
        return checks

    try:
        actions_payload = json.loads(actions_path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.append(("Pet action manifest", False, f"invalid JSON: {exc}"))
        return checks

    actions = actions_payload.get("actions", {})
    checks.append(("Pet action manifest", bool(actions), f"{len(actions)} action(s)"))
    actions_root = actions_path.parent
    optional_missing: list[str] = []
    for action_id, raw in actions.items():
        if not isinstance(raw, dict):
            continue
        file_name = str(raw.get("file", "")).strip()
        fallback = str(raw.get("fallback", "")).strip()
        if file_name and not (actions_root / file_name).exists():
            optional_missing.append(f"{action_id}->{fallback or 'idle'}")
    checks.append(
        (
            "Pet action fallback coverage",
            True,
            "optional missing strips use fallback: " + ", ".join(optional_missing)
            if optional_missing
            else "all custom strips present",
        )
    )
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
