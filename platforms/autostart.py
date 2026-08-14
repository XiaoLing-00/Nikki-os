from __future__ import annotations

import platform
import plistlib
import sys
from pathlib import Path

APP_ID = "com.soulpet.nikki-os"


def set_auto_start(enabled: bool, project_root: Path) -> tuple[bool, str]:
    system = platform.system()
    command = _launch_command(project_root)
    try:
        if system == "Windows":
            return _set_windows(enabled, command)
        if system == "Darwin":
            return _set_macos(enabled, command)
        return False, f"{system} 暂不支持自动启动设置"
    except Exception as exc:
        return False, str(exc)


def _launch_command(project_root: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(project_root / "main.py")]


def _set_windows(enabled: bool, command: list[str]) -> tuple[bool, str]:
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            quoted = " ".join(f'"{part}"' for part in command)
            winreg.SetValueEx(key, "Nikki-os", 0, winreg.REG_SZ, quoted)
        else:
            try:
                winreg.DeleteValue(key, "Nikki-os")
            except FileNotFoundError:
                pass
    return True, "Windows 登录启动项已更新"


def _set_macos(enabled: bool, command: list[str]) -> tuple[bool, str]:
    target = Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": APP_ID,
            "ProgramArguments": command,
            "RunAtLoad": True,
            "KeepAlive": False,
        }
        target.write_bytes(plistlib.dumps(payload))
    elif target.exists():
        target.unlink()
    return True, "macOS 登录启动项已更新"
