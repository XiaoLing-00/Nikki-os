from __future__ import annotations

import importlib.util
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings


@dataclass(frozen=True)
class Check:
    name: str
    level: str
    detail: str
    fix: str = ""


def run_doctor(settings: Settings, check_api: bool = False) -> int:
    checks: list[Check] = []
    checks.append(
        Check(
            "Python",
            "OK" if sys.version_info >= (3, 10) else "FAIL",
            f"{platform.python_version()} ({platform.system()} {platform.machine()})",
            "请安装 Python 3.10 或更高版本。",
        )
    )
    checks.extend(_dependency_checks(settings.renderer_backend))
    checks.append(
        Check(
            "env file",
            "OK" if settings.env_file_path else "WARN",
            str(settings.env_file_path) if settings.env_file_path else "未找到 .env；离线桌宠仍可运行。",
            "复制 .env.example 为 .env，然后填写 DASHSCOPE_API_KEY。",
        )
    )
    checks.append(
        Check(
            "DASHSCOPE_API_KEY",
            "OK" if settings.dashscope_api_key else "WARN",
            f"loaded length={len(settings.dashscope_api_key or '')}" if settings.dashscope_api_key else "未配置；AI、视觉和语音功能禁用。",
            "在项目根目录 .env 中配置 DASHSCOPE_API_KEY。",
        )
    )
    checks.extend(_check_sprite_assets(settings.sprite_manifest_path))
    checks.extend(_check_live2d_assets(settings.live2d_model_path))
    checks.append(_check_microphone())
    if check_api:
        ok, detail = _ping_dashscope(settings)
        checks.append(Check("DashScope ping", "OK" if ok else "FAIL", detail, "检查 API Key、模型地域和网络连接。"))

    print("Nikki-os Doctor")
    print("=" * 64)
    print(f"renderer: {settings.renderer_backend}")
    for check in checks:
        print(f"[{check.level}] {check.name}: {check.detail}")
        if check.level != "OK" and check.fix:
            print(f"       fix: {check.fix}")
    failures = [check for check in checks if check.level == "FAIL"]
    print("=" * 64)
    print(f"result: {'FAIL' if failures else 'PASS'} ({len(failures)} failure(s))")
    return 1 if failures else 0


def _dependency_checks(renderer: str) -> list[Check]:
    required = {
        "requests": "requests",
        "psutil": "psutil",
        "jsonschema": "jsonschema",
        "PyQt6": "PyQt6",
    }
    if renderer == "live2d":
        required["PyQt6-WebEngine"] = "PyQt6.QtWebEngineWidgets"
    optional = {"DashScope SDK": "dashscope", "PyAudio": "pyaudio"}
    checks = [
        Check(
            name,
            "OK" if importlib.util.find_spec(module) else "FAIL",
            "installed" if importlib.util.find_spec(module) else "missing",
            f"{sys.executable} -m pip install {name}",
        )
        for name, module in required.items()
    ]
    checks.extend(
        Check(
            name,
            "OK" if importlib.util.find_spec(module) else "WARN",
            "installed" if importlib.util.find_spec(module) else "missing; related feature disabled",
            f"{sys.executable} -m pip install {module}",
        )
        for name, module in optional.items()
    )
    return checks


def _check_sprite_assets(manifest_path: Path) -> list[Check]:
    if not manifest_path.exists():
        return [Check("sprite manifest", "FAIL", f"missing: {manifest_path}", "重新安装 assets/sprites 资源。")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        atlas_path = manifest_path.parent / manifest["atlas"]
        required_states = {"idle", "talking", "thinking", "listening", "happy", "sad", "error", "dragging"}
        missing_states = sorted(required_states.difference(manifest.get("states", {})))
        checks = [Check("sprite manifest", "OK" if not missing_states else "FAIL", f"states={len(manifest.get('states', {}))}; missing={missing_states or 'none'}")]
        checks.append(Check("sprite atlas", "OK" if atlas_path.exists() else "FAIL", str(atlas_path)))
        if atlas_path.exists():
            try:
                from PIL import Image

                with Image.open(atlas_path) as image:
                    expected = (
                        int(manifest["columns"]) * int(manifest["cell_width"]),
                        int(manifest["rows"]) * int(manifest["cell_height"]),
                    )
                    checks.append(Check("sprite dimensions", "OK" if image.size == expected else "FAIL", f"actual={image.size} expected={expected} mode={image.mode}"))
            except Exception as exc:
                checks.append(Check("sprite dimensions", "WARN", f"not inspected: {exc}", "安装 Pillow 后重新运行 Doctor。"))
        return checks
    except Exception as exc:
        return [Check("sprite manifest", "FAIL", f"invalid: {exc}", "修复 manifest.json。")]


def _check_live2d_assets(model_path: Path) -> list[Check]:
    if not model_path.exists():
        return [Check("Live2D model", "FAIL", f"missing: {model_path}")]
    try:
        model = json.loads(model_path.read_text(encoding="utf-8-sig"))
        refs = model.get("FileReferences", {})
        root = model_path.parent
        files = [refs.get("Moc", ""), refs.get("Physics", ""), *refs.get("Textures", [])]
        files.extend(item.get("File", "") for motions in refs.get("Motions", {}).values() for item in motions)
        files.extend(item.get("File", "") for item in refs.get("Expressions", []))
        missing = [item for item in files if item and not (root / item).exists()]
        return [Check("Live2D references", "OK" if not missing else "FAIL", f"missing={missing or 'none'}")]
    except Exception as exc:
        return [Check("Live2D model", "FAIL", f"invalid JSON: {exc}")]


def _check_microphone() -> Check:
    if not importlib.util.find_spec("pyaudio"):
        return Check("microphone", "WARN", "PyAudio missing; voice input disabled", f"{sys.executable} -m pip install PyAudio")
    try:
        import pyaudio

        audio = pyaudio.PyAudio()
        count = audio.get_device_count()
        inputs = sum(1 for index in range(count) if audio.get_device_info_by_index(index).get("maxInputChannels", 0) > 0)
        audio.terminate()
        return Check("microphone", "OK" if inputs else "WARN", f"input devices={inputs}", "检查系统麦克风权限。")
    except Exception as exc:
        return Check("microphone", "WARN", str(exc), "检查麦克风设备与系统权限。")


def _ping_dashscope(settings: Settings) -> tuple[bool, str]:
    if not settings.dashscope_api_key:
        return False, "skip: DASHSCOPE_API_KEY not loaded"
    try:
        import requests

        response = requests.post(
            f"{settings.dashscope_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"},
            json={"model": settings.text_model, "messages": [{"role": "user", "content": "只回复 OK"}], "temperature": 0, "max_tokens": 8},
            timeout=15,
        )
        if response.ok:
            return True, f"{response.status_code}: {response.json()['choices'][0]['message']['content'][:20]}"
        return False, f"{response.status_code}: {response.text[:200]}"
    except Exception as exc:
        return False, str(exc)
