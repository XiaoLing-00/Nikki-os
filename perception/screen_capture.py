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


def classify_app(title: str, process_name: str = "") -> str:
    lowered = title.lower()
    process = process_name.lower()
    if "visual studio code" in lowered or "vs code" in lowered or process in {"code.exe", "pycharm64.exe", "idea64.exe"}:
        return "VS Code"
    if "bilibili" in lowered or "哔哩哔哩" in lowered or "b站" in lowered:
        return "Bilibili"
    if "chrome" in lowered or "edge" in lowered or "firefox" in lowered or process in {"chrome.exe", "msedge.exe", "firefox.exe"}:
        return "Browser"
    if "word" in lowered or process == "winword.exe":
        return "Word"
    if "powerpoint" in lowered or process == "powerpnt.exe":
        return "PowerPoint"
    if "wps" in lowered or process in {"wps.exe", "wpp.exe"}:
        return "WPS"
    return title.split(" - ")[-1].strip() if title else "Unknown"


def capture_primary_screen(path: Path) -> Path | None:
    from PyQt6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = screen.grabWindow(0)
    return path if pixmap.save(str(path), "PNG") else None
