from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SpeechBubble(QWidget):
    submitted = pyqtSignal(str)
    voice_requested = pyqtSignal()
    menu_requested = pyqtSignal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.expanded = False
        self.compact_height = 78
        self.expanded_height = 132
        self.bubble_width = 326

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("speechWindow")

        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("bubbleCard")
        shell.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.speech_label = QLabel("暖暖在这里陪你。")
        self.speech_label.setWordWrap(True)
        self.speech_label.setObjectName("speech")
        top_row.addWidget(self.speech_label, 1)

        self.menu_button = QPushButton("...")
        self.menu_button.setObjectName("menuButton")
        self.menu_button.setFixedSize(30, 28)
        self.menu_button.setToolTip("菜单")
        self.menu_button.clicked.connect(self._emit_menu)
        top_row.addWidget(self.menu_button)
        layout.addLayout(top_row)

        self.input_row = QHBoxLayout()
        self.input_row.setContentsMargins(0, 0, 0, 0)
        self.input_row.setSpacing(8)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("和暖暖说点什么...")
        self.input_line.returnPressed.connect(self._submit)
        self.input_row.addWidget(self.input_line, 1)

        self.voice_button = QPushButton("语音")
        self.voice_button.setObjectName("voiceButton")
        self.voice_button.setToolTip("语音输入")
        self.voice_button.clicked.connect(self.voice_requested.emit)
        self.input_row.addWidget(self.voice_button)

        self.say_button = QPushButton("发送")
        self.say_button.clicked.connect(self._submit)
        self.input_row.addWidget(self.say_button)
        layout.addLayout(self.input_row)

        self.setStyleSheet(
            """
            #speechWindow { background: transparent; }
            #bubbleCard {
                background: rgba(255, 250, 253, 242);
                border: 1px solid rgba(233, 136, 177, 150);
                border-radius: 8px;
            }
            #speech {
                color: #4a2433;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-size: 14px;
                line-height: 1.4;
                min-height: 34px;
            }
            QLineEdit {
                min-height: 34px;
                border: 1px solid rgba(233, 136, 177, 150);
                border-radius: 7px;
                padding: 0 10px;
                color: #4a2433;
                background: rgba(255, 255, 255, 245);
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
            QPushButton {
                min-height: 30px;
                min-width: 54px;
                border: 0;
                border-radius: 7px;
                color: white;
                background: #e85f98;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
            QPushButton:hover { background: #d94f88; }
            QPushButton:disabled { background: rgba(168, 130, 150, 150); }
            #voiceButton { background: #7b8fd6; }
            #voiceButton:hover { background: #6d80c8; }
            #menuButton {
                min-width: 30px;
                min-height: 28px;
                color: #7a4058;
                background: rgba(255, 229, 240, 220);
            }
            #menuButton:hover { background: rgba(255, 214, 231, 240); }
            """
        )
        self.set_expanded(False)

    def set_text(self, text: str) -> None:
        self.speech_label.setText(text)

    def set_placeholder(self, text: str) -> None:
        self.input_line.setPlaceholderText(text)

    def set_expanded(self, expanded: bool, focus_input: bool = False) -> None:
        self.expanded = expanded
        for index in range(self.input_row.count()):
            item = self.input_row.itemAt(index)
            if item and item.widget():
                item.widget().setVisible(expanded)
        self.resize(self.bubble_width, self.expanded_height if expanded else self.compact_height)
        if expanded and focus_input:
            self.input_line.setFocus(Qt.FocusReason.MouseFocusReason)
        elif not expanded:
            self.input_line.clearFocus()

    def show_near(self, anchor: QRect, expanded: bool = False, focus_input: bool = False) -> None:
        self.set_expanded(expanded, focus_input=False)
        self.move(self._position_near(anchor))
        self.show()
        self.raise_()
        if expanded and focus_input:
            self.input_line.setFocus(Qt.FocusReason.MouseFocusReason)

    def has_input_focus(self) -> bool:
        return self.input_line.hasFocus()

    def has_interaction_focus(self) -> bool:
        focused = QApplication.focusWidget()
        return any(
            focused is widget
            for widget in (
                self.input_line,
                self.voice_button,
                self.say_button,
                self.menu_button,
            )
        )

    def has_pending_input(self) -> bool:
        return bool(self.input_line.text().strip())

    def should_stay_open(self) -> bool:
        return self.expanded or self.has_interaction_focus() or self.has_pending_input()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.input_line.setEnabled(enabled)
        self.say_button.setEnabled(enabled)
        self.voice_button.setEnabled(enabled)

    def set_voice_recording(self, recording: bool) -> None:
        self.voice_button.setText("结束录音" if recording else "语音")

    def text(self) -> str:
        return self.input_line.text()

    def clear_text(self) -> None:
        self.input_line.clear()

    def _submit(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self.submitted.emit(text)

    def _emit_menu(self) -> None:
        self.menu_requested.emit(self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height())))

    def _position_near(self, anchor: QRect) -> QPoint:
        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        margin = 10
        width = self.width()
        height = self.height()

        right = QPoint(anchor.right() + margin, anchor.center().y() - height // 2)
        if right.x() + width <= available.right():
            return self._clamp(right, available)

        left = QPoint(anchor.left() - width - margin, anchor.center().y() - height // 2)
        if left.x() >= available.left():
            return self._clamp(left, available)

        above = QPoint(anchor.center().x() - width // 2, anchor.top() - height - margin)
        if above.y() >= available.top():
            return self._clamp(above, available)

        below = QPoint(anchor.center().x() - width // 2, anchor.bottom() + margin)
        return self._clamp(below, available)

    def _clamp(self, pos: QPoint, available: QRect) -> QPoint:
        x = max(available.left(), min(pos.x(), available.right() - self.width()))
        y = max(available.top(), min(pos.y(), available.bottom() - self.height()))
        return QPoint(x, y)
