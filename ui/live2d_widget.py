from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget


class Live2DBridge(QObject):
    ready = pyqtSignal(str)
    log = pyqtSignal(str)

    @pyqtSlot(str)
    def onReady(self, message: str) -> None:
        self.ready.emit(message)

    @pyqtSlot(str)
    def onLog(self, message: str) -> None:
        self.log.emit(message)


class Live2DPage(QWebEnginePage):
    console_message = pyqtSignal(str)

    def javaScriptConsoleMessage(self, level, message: str, line_number: int, source_id: str) -> None:
        source = Path(source_id).name if source_id else "viewer"
        self.console_message.emit(f"{source}:{line_number} {message}")


class Live2DWidget(QWebEngineView):
    def __init__(
        self,
        viewer_path: Path,
        model_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.viewer_path = viewer_path
        self.model_path = model_path
        self.web_page = Live2DPage(self)
        self.setPage(self.web_page)
        self.bridge = Live2DBridge()
        self.channel = QWebChannel(self.page())
        self.channel.registerObject("pythonBridge", self.bridge)
        self.page().setWebChannel(self.channel)
        self.web_page.console_message.connect(self.bridge.onLog)
        self._configure_web_engine()
        self.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: transparent; border: 0;")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.installEventFilter(parent) if parent else None
        self.focusProxy().installEventFilter(parent) if self.focusProxy() and parent else None
        self.load(QUrl.fromLocalFile(str(self.viewer_path)))

    def _configure_web_engine(self) -> None:
        settings = self.page().settings()
        attrs = QWebEngineSettings.WebAttribute
        for attr in (
            attrs.JavascriptEnabled,
            attrs.LocalStorageEnabled,
            attrs.LocalContentCanAccessFileUrls,
            attrs.LocalContentCanAccessRemoteUrls,
            attrs.WebGLEnabled,
            attrs.Accelerated2dCanvasEnabled,
            attrs.AllowRunningInsecureContent,
            attrs.ReadingFromCanvasEnabled,
        ):
            settings.setAttribute(attr, True)
        settings.setAttribute(attrs.ShowScrollBars, False)

    def set_expression(self, expression: str) -> None:
        self._run_js(f"window.SoulPet && window.SoulPet.setExpression({expression!r});")

    def play_motion(self, motion: str) -> None:
        self._run_js(f"window.SoulPet && window.SoulPet.playMotion({motion!r});")

    def speak(self, expression: str, motion: str) -> None:
        self._run_js(
            "window.SoulPet && window.SoulPet.speak("
            f"{expression!r}, {motion!r});"
        )

    def set_pointer_enabled(self, enabled: bool) -> None:
        value = "true" if enabled else "false"
        self._run_js(f"window.SoulPet && window.SoulPet.setPointerEnabled({value});")

    def refresh_viewport(self) -> None:
        self._run_js("window.SoulPet && window.SoulPet.refreshViewport();")

    def set_idle_state(self, state: str) -> None:
        self._run_js(f"window.SoulPet && window.SoulPet.setIdleState({state!r});")

    def _run_js(self, script: str) -> None:
        self.page().runJavaScript(script)
