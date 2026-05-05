from __future__ import annotations

from pathlib import Path

try:
    import pygetwindow as gw
except Exception:  # pragma: no cover - optional platform dependency
    gw = None

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None


def get_active_window_title() -> str:
    if gw is None:
        return ""
    try:
        window = gw.getActiveWindow()
    except Exception:
        return ""
    return window.title if window and window.title else ""


def get_active_process_name() -> str:
    if psutil is None:
        return ""
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        return psutil.Process(pid.value).name()
    except Exception:
        return ""


def classify_app(title: str) -> str:
    lowered = title.lower()
    if "visual studio code" in lowered or "vs code" in lowered or "code.exe" in lowered:
        return "VS Code"
    if "bilibili" in lowered or "哔哩哔哩" in lowered or "b站" in lowered:
        return "Bilibili"
    if "chrome" in lowered or "edge" in lowered or "firefox" in lowered:
        return "Browser"
    if "word" in lowered:
        return "Word"
    if "powerpoint" in lowered:
        return "PowerPoint"
    return title.split(" - ")[-1].strip() if title else "Unknown"


def capture_primary_screen(path: Path) -> Path | None:
    from PyQt6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = screen.grabWindow(0)
    return path if pixmap.save(str(path), "PNG") else None
