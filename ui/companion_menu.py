from __future__ import annotations

from collections.abc import Callable

import qtawesome as qta
from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class CompanionMenu(QWidget):
    """Warm, compact popup menu shared by the desktop companion surface."""

    EXPRESSION_LABELS = (
        ("wink", "眨眼"),
        ("love", "喜欢"),
        ("cry", "难过"),
        ("awkward", "害羞"),
        ("dizzy", "晕乎乎"),
        ("rose", "送花"),
        ("punch", "加油"),
    )

    def __init__(
        self,
        *,
        open_settings: Callable[[], None],
        open_memory: Callable[[], None],
        analyze_screen: Callable[[], None],
        like_reminder: Callable[[], None],
        reduce_reminder: Callable[[], None],
        preview_expression: Callable[[str], None],
        quit_app: Callable[[], None],
        open_live2d_debugger: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("companionMenuPopup")
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 16)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.surface = QFrame()
        self.surface.setObjectName("companionMenuSurface")
        self.surface.setFixedWidth(258)
        shadow = QGraphicsDropShadowEffect(self.surface)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(83, 44, 61, 55))
        self.surface.setGraphicsEffect(shadow)
        outer.addWidget(self.surface)

        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(10, 10, 10, 10)
        surface_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("companionMenuStack")
        surface_layout.addWidget(self.stack)

        self.main_page = self._build_main_page(
            open_settings=open_settings,
            open_memory=open_memory,
            analyze_screen=analyze_screen,
            like_reminder=like_reminder,
            reduce_reminder=reduce_reminder,
            quit_app=quit_app,
        )
        self.tools_page = self._build_tools_page(
            preview_expression=preview_expression,
            open_live2d_debugger=open_live2d_debugger,
        )
        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.tools_page)

        self.setStyleSheet(
            """
            QWidget {
                font-family: 'PingFang SC', 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
            }
            #companionMenuSurface {
                background: rgba(255, 251, 253, 250);
                border: 1px solid rgba(235, 153, 184, 170);
                border-radius: 16px;
            }
            #companionMenuStack, #menuMainPage, #menuToolsPage {
                background: transparent;
                border: none;
            }
            #menuTitle {
                color: #9b6b7c;
                font-size: 12px;
                font-weight: 600;
                padding: 1px 10px 5px 10px;
            }
            QPushButton[menuRole="item"] {
                min-height: 37px;
                max-height: 37px;
                border: none;
                border-radius: 10px;
                background: transparent;
                color: #542c3b;
                font-size: 14px;
                font-weight: 400;
                text-align: left;
                padding: 0 10px;
            }
            QPushButton[menuRole="item"]:hover,
            QPushButton[menuRole="item"]:focus {
                background: rgba(248, 225, 235, 220);
                color: #b83f70;
            }
            QPushButton[menuRole="feedback"] {
                min-height: 35px;
                max-height: 35px;
                border: 1px solid rgba(235, 153, 184, 105);
                border-radius: 10px;
                background: rgba(255, 255, 255, 170);
                color: #713548;
                font-size: 13px;
                padding: 0 8px;
            }
            QPushButton[menuRole="feedback"]:hover,
            QPushButton[menuRole="feedback"]:focus {
                border-color: rgba(226, 101, 149, 150);
                background: rgba(248, 225, 235, 230);
                color: #b83f70;
            }
            QPushButton[menuRole="expression"] {
                min-height: 35px;
                max-height: 35px;
                border: 1px solid rgba(235, 153, 184, 95);
                border-radius: 10px;
                background: rgba(255, 255, 255, 170);
                color: #713548;
                font-size: 13px;
                padding: 0 8px;
            }
            QPushButton[menuRole="expression"]:hover,
            QPushButton[menuRole="expression"]:focus {
                border-color: rgba(226, 101, 149, 150);
                background: rgba(248, 225, 235, 230);
                color: #b83f70;
            }
            QPushButton[menuRole="item"][danger="true"] { color: #b84266; }
            QPushButton[menuRole="item"][danger="true"]:hover,
            QPushButton[menuRole="item"][danger="true"]:focus {
                background: rgba(255, 224, 233, 235);
                color: #a72f56;
            }
            QFrame[menuRole="separator"] {
                background: rgba(222, 188, 201, 120);
                border: none;
                min-height: 1px;
                max-height: 1px;
                margin: 5px 8px;
            }
            """
        )

    def _build_main_page(
        self,
        *,
        open_settings: Callable[[], None],
        open_memory: Callable[[], None],
        analyze_screen: Callable[[], None],
        like_reminder: Callable[[], None],
        reduce_reminder: Callable[[], None],
        quit_app: Callable[[], None],
    ) -> QWidget:
        page = QWidget()
        page.setObjectName("menuMainPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel("暖暖菜单")
        title.setObjectName("menuTitle")
        layout.addWidget(title)

        self.settings_button = self._item_button("fa6s.gear", "设置", open_settings)
        self.memory_button = self._item_button("fa6s.brain", "记忆管理", open_memory)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.memory_button)
        layout.addWidget(self._separator())

        self.analyze_button = self._item_button(
            "fa6s.display",
            "分析屏幕",
            analyze_screen,
            tooltip="会先请你确认截图",
        )
        layout.addWidget(self.analyze_button)

        feedback_row = QHBoxLayout()
        feedback_row.setContentsMargins(0, 0, 0, 0)
        feedback_row.setSpacing(6)
        self.like_button = self._compact_button("fa6s.heart", "喜欢提醒", like_reminder)
        self.reduce_button = self._compact_button("fa6s.bell-slash", "减少此类", reduce_reminder)
        feedback_row.addWidget(self.like_button)
        feedback_row.addWidget(self.reduce_button)
        layout.addLayout(feedback_row)
        layout.addWidget(self._separator())

        self.more_button = self._item_button(
            "fa6s.ellipsis",
            "更多工具",
            self.show_tools,
            trailing_icon="fa6s.chevron-right",
        )
        layout.addWidget(self.more_button)

        self.quit_button = self._item_button(
            "fa6s.power-off",
            "退出暖暖",
            quit_app,
            danger=True,
        )
        layout.addWidget(self.quit_button)
        return page

    def _build_tools_page(
        self,
        *,
        preview_expression: Callable[[str], None],
        open_live2d_debugger: Callable[[], None] | None,
    ) -> QWidget:
        page = QWidget()
        page.setObjectName("menuToolsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.back_button = self._item_button("fa6s.arrow-left", "更多工具", self.show_main)
        layout.addWidget(self.back_button)
        layout.addWidget(self._separator())

        title = QLabel("测试表情")
        title.setObjectName("menuTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.expression_buttons: dict[str, QPushButton] = {}
        for index, (name, label) in enumerate(self.EXPRESSION_LABELS):
            button = self._expression_button(
                label,
                lambda expression=name: preview_expression(expression),
            )
            button.setAccessibleName(f"测试表情：{label}")
            self.expression_buttons[name] = button
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)

        if open_live2d_debugger is not None:
            layout.addWidget(self._separator())
            self.live2d_button = self._item_button(
                "fa6s.code",
                "Live2D 参数调试",
                open_live2d_debugger,
            )
            layout.addWidget(self.live2d_button)
        else:
            self.live2d_button = None
        return page

    def _item_button(
        self,
        icon_name: str,
        text: str,
        callback: Callable[[], None],
        *,
        role: str = "item",
        danger: bool = False,
        tooltip: str = "",
        trailing_icon: str | None = None,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("menuRole", role)
        button.setProperty("danger", danger)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(qta.icon(icon_name, color="#9c526c"))
        button.setIconSize(QSize(15, 15))
        button.setAccessibleName(text)
        if tooltip:
            button.setToolTip(tooltip)
        button.clicked.connect(lambda _checked=False: self._activate(callback))
        if trailing_icon:
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.setIcon(qta.icon(trailing_icon, color="#b68596"))
        return button

    def _compact_button(
        self,
        icon_name: str,
        text: str,
        callback: Callable[[], None],
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("menuRole", "feedback")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(qta.icon(icon_name, color="#b85b7d"))
        button.setIconSize(QSize(14, 14))
        button.setAccessibleName(text)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(lambda _checked=False: self._activate(callback))
        return button

    def _expression_button(self, text: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("menuRole", "expression")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(lambda _checked=False: self._activate(callback))
        return button

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setProperty("menuRole", "separator")
        line.setFrameShape(QFrame.Shape.NoFrame)
        return line

    def _activate(self, callback: Callable[[], None]) -> None:
        if callback in (self.show_main, self.show_tools):
            callback()
            return
        self.hide()
        QTimer.singleShot(0, callback)

    def show_main(self) -> None:
        self.stack.setCurrentWidget(self.main_page)
        self.settings_button.setFocus(Qt.FocusReason.PopupFocusReason)

    def show_tools(self) -> None:
        self.stack.setCurrentWidget(self.tools_page)
        self.back_button.setFocus(Qt.FocusReason.PopupFocusReason)

    def show_at(self, position: QPoint) -> None:
        self.show_main()
        self.adjustSize()
        screen = QApplication.screenAt(position) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        size = self.sizeHint()
        x = min(max(position.x(), available.left()), available.right() - size.width() + 1)
        if position.y() + size.height() <= available.bottom() + 1:
            y = position.y()
        else:
            y = max(available.top(), position.y() - size.height())
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)
