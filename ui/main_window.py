from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

import qtawesome as qta
from PyQt6.QtCore import QObject, QPoint, QRect, QRunnable, QSize, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from agents.observer_agent import ObserverAgent
from agents.persona_agent import PersonaAgent
from animation.action_mapper import ActionMapper
from animation.state_machine import AnimationStateMachine
from animation.states import AnimationState
from config.preferences import PreferencesStore
from config.settings import Settings
from perception.context_builder import ContextBuilder
from renderers.factory import create_renderer
from services.asr_service import ASRService
from services.tts_service import TTSService
from ui.companion_menu import CompanionMenu
from ui.live2d_debug_dialog import Live2DParameterDialog
from ui.settings_dialog import MemoryDialog, SettingsDialog
from utils.metrics import record_metric


@dataclass
class AgentTask:
    user_text: str
    context: dict
    proactive: bool = False


class WorkerSignals(QObject):
    finished = pyqtSignal(dict)


class AgentWorker(QRunnable):
    def __init__(self, agent: PersonaAgent, task: AgentTask) -> None:
        super().__init__()
        self.agent = agent
        self.task = task
        self.signals = WorkerSignals()

    def run(self) -> None:
        started = perf_counter()
        success = True
        try:
            result = self.agent.reply(
                self.task.user_text,
                self.task.context,
                proactive=self.task.proactive,
            )
        except Exception as exc:
            success = False
            print(f"[Agent] worker failed: {exc}")
            result = {
                "response": {
                    "text": "哎呀，暖暖思考时走神了，不过我还在晓灵旁边呀。",
                    "emotion": "awkward",
                    "action": "motion_idle",
                }
            }
        result["_reply_meta"] = {"proactive": self.task.proactive}
        self.signals.finished.emit(result)
        record_metric(
            "agent_reply",
            latency_ms=round((perf_counter() - started) * 1000, 1),
            proactive=self.task.proactive,
            success=success,
        )


class VisualAgentWorker(QRunnable):
    def __init__(
        self,
        context_builder: ContextBuilder,
        agent: PersonaAgent,
        user_text: str,
        proactive: bool = False,
        approved_image_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.context_builder = context_builder
        self.agent = agent
        self.user_text = user_text
        self.proactive = proactive
        self.approved_image_path = approved_image_path
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            context = self.context_builder.build_visual_context(self.approved_image_path)
            result = self.agent.reply(self.user_text, context, proactive=self.proactive)
        except Exception as exc:
            print(f"[Agent] visual worker failed: {exc}")
            result = {
                "response": {
                    "text": "唔，暖暖刚刚看屏幕时卡住了，但没有保存截图哒。",
                    "emotion": "awkward",
                    "action": "motion_idle",
                }
            }
        result["_reply_meta"] = {"proactive": self.proactive}
        self.signals.finished.emit(result)


class ASRTranscribeWorker(QRunnable):
    def __init__(self, asr_service: ASRService) -> None:
        super().__init__()
        self.asr_service = asr_service
        self.signals = WorkerSignals()

    def run(self) -> None:
        text = self.asr_service.stop_and_transcribe()
        self.signals.finished.emit({"text": text})


class TTSWorker(QRunnable):
    def __init__(self, tts_service: TTSService, text: str) -> None:
        super().__init__()
        self.tts_service = tts_service
        self.text = text
        self.signals = WorkerSignals()

    def run(self) -> None:
        path = self.tts_service.synthesize_online(self.text)
        self.signals.finished.emit({"audio_path": str(path) if path else ""})


class MainWindow(QWidget):
    def __init__(
        self,
        settings: Settings,
        context_builder: ContextBuilder,
        observer_agent: ObserverAgent,
        persona_agent: PersonaAgent,
        asr_service: ASRService,
        preferences: PreferencesStore | None = None,
        tts_service: TTSService | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.context_builder = context_builder
        self.observer_agent = observer_agent
        self.persona_agent = persona_agent
        self.asr_service = asr_service
        self.preferences = preferences or PreferencesStore()
        self.tts_service = tts_service or TTSService(settings, self.preferences, self)
        self.actions = ActionMapper()
        self.animation = AnimationStateMachine(self)
        self.thread_pool = QThreadPool.globalInstance()
        self.drag_offset: QPoint | None = None
        self.press_pos: QPoint | None = None
        self.busy = False
        self.dragging = False
        self.recording_voice = False
        self.hovered = False
        self.voice_key_active = False
        self.roam_direction = -1
        self._last_proactive_reason: str | None = None
        self._tts_request_id = 0
        self._pending_user_text: str | None = None
        self._active_task_proactive = False
        self._last_user_reply_at: datetime | None = None
        self._companion_menu: CompanionMenu | None = None

        self._setup_window()
        self._setup_ui()
        self._setup_timers()
        self._setup_tray()

    def _setup_window(self) -> None:
        self.setWindowTitle("苏暖暖")
        self.resize(430, 660)
        preferences = self.preferences.load()
        if preferences.remember_window_position and preferences.window_x is not None and preferences.window_y is not None:
            self.move(preferences.window_x, preferences.window_y)
        else:
            self.move(QApplication.primaryScreen().availableGeometry().right() - 470, 120)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setContentsMargins(0, 0, 0, 0)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setStyleSheet("MainWindow { background: transparent; border: 0; }")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._remove_native_border()

    def _setup_ui(self) -> None:
        self.live2d = create_renderer(self.settings, self)
        self.live2d.setGeometry(0, 0, self.width(), self.height())
        self.live2d.show()
        if hasattr(self.live2d, "bridge"):
            self.live2d.bridge.log.connect(self._display_live2d_log)
            self.live2d.bridge.ready.connect(self._display_live2d_log)
        self.animation.state_changed.connect(self.live2d.play_state)

        self.bubble = QFrame(self)
        self.bubble.setObjectName("bubble")
        self.bubble.setGeometry(24, 18, 382, 144)
        self.bubble.hide()
        self._add_shadow(self.bubble, blur=24, y_offset=6, alpha=44)

        layout = QVBoxLayout(self.bubble)
        layout.setContentsMargins(16, 14, 14, 14)
        layout.setSpacing(10)

        self.speech_label = QLabel("暖暖在这里陪你呀。")
        self.speech_label.setWordWrap(True)
        self.speech_label.setObjectName("speech")
        layout.addWidget(self.speech_label)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("和暖暖说点什么呀...")
        self.input_line.returnPressed.connect(self._submit_user_text)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)
        input_row.addWidget(self.input_line, 1)

        self.voice_button = QPushButton("语音")
        self.voice_button.setObjectName("voiceButton")
        self.voice_button.setToolTip("语音输入")
        self.voice_button.setAccessibleName("语音输入")
        self.voice_button.setText("")
        self.voice_button.setIcon(qta.icon("fa6s.microphone", color="#ffffff"))
        self.voice_button.setIconSize(QSize(15, 15))
        self.voice_button.setFixedSize(38, 38)
        self.voice_button.clicked.connect(self._toggle_voice_input)
        input_row.addWidget(self.voice_button)

        self.say_button = QPushButton()
        self.say_button.setObjectName("sayButton")
        self.say_button.setToolTip("发送消息")
        self.say_button.setAccessibleName("发送消息")
        self.say_button.setIcon(qta.icon("fa6s.paper-plane", color="#ffffff"))
        self.say_button.setIconSize(QSize(15, 15))
        self.say_button.setFixedSize(38, 38)
        self.say_button.clicked.connect(self._submit_user_text)
        input_row.addWidget(self.say_button)
        layout.addLayout(input_row)

        self.hover_prompt = QFrame(self)
        self.hover_prompt.setObjectName("hoverPrompt")
        self.hover_prompt.setGeometry(123, 84, 184, 48)
        self.hover_prompt.hide()
        self._add_shadow(self.hover_prompt, blur=18, y_offset=5, alpha=40)
        hover_layout = QHBoxLayout(self.hover_prompt)
        hover_layout.setContentsMargins(8, 2, 2, 2)
        hover_layout.setSpacing(0)
        self.hover_text_button = QPushButton("和暖暖说话")
        self.hover_text_button.setObjectName("hoverTextButton")
        self.hover_text_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hover_text_button.setAccessibleName("打开暖暖聊天框")
        self.hover_text_button.clicked.connect(self._open_chat)
        hover_layout.addWidget(self.hover_text_button, 1)
        self.hover_chat_button = QPushButton()
        self.hover_chat_button.setObjectName("hoverChatButton")
        self.hover_chat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hover_chat_button.setAccessibleName("打开暖暖聊天框")
        self.hover_chat_button.setIcon(qta.icon("mdi6.comment-processing-outline", color="#ffffff"))
        self.hover_chat_button.setIconSize(QSize(19, 19))
        self.hover_chat_button.setFixedSize(44, 44)
        self.hover_chat_button.clicked.connect(self._open_chat)
        hover_layout.addWidget(self.hover_chat_button)

        self.setStyleSheet(
            """
            MainWindow { background: transparent; border: 0; }
            QWidget { font-family: 'PingFang SC', 'Microsoft YaHei UI', 'Segoe UI', sans-serif; }
            #bubble {
                background: rgba(255, 252, 254, 246);
                border: 1px solid rgba(235, 153, 184, 155);
                border-radius: 18px;
            }
            #speech {
                color: #542c3b;
                font-size: 14px;
                line-height: 1.4;
                min-height: 38px;
            }
            QLineEdit {
                min-height: 36px;
                border: 1px solid rgba(231, 160, 189, 190);
                border-radius: 12px;
                padding: 0 12px;
                color: #542c3b;
                background: rgba(255, 255, 255, 248);
            }
            QLineEdit:focus { border: 1px solid #eb6a9d; }
            #voiceButton, #sayButton {
                border: none;
                border-radius: 19px;
                color: white;
                background: #eb5d95;
            }
            #voiceButton { background: #8a98d9; }
            #voiceButton:hover { background: #7888cf; }
            #sayButton:hover { background: #df4f88; }
            #voiceButton:disabled, #sayButton:disabled { background: rgba(174, 151, 163, 175); }
            #hoverPrompt {
                background: rgba(255, 250, 252, 246);
                border: 1px solid rgba(246, 190, 211, 120);
                border-radius: 24px;
            }
            #hoverTextButton {
                border: none;
                background: transparent;
                color: #713548;
                font-size: 14px;
                font-weight: 400;
                text-align: center;
                padding: 0 5px 0 9px;
            }
            #hoverTextButton:hover { color: #d94f88; }
            #hoverChatButton {
                border: none;
                border-radius: 22px;
                background: #eb5d95;
            }
            #hoverChatButton:hover { background: #df4f88; }
            """
        )

    @staticmethod
    def _add_shadow(widget: QWidget, blur: int, y_offset: int, alpha: int) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(83, 44, 61, alpha))
        widget.setGraphicsEffect(shadow)

    def resizeEvent(self, event) -> None:
        if hasattr(self, "live2d"):
            self.live2d.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def _remove_native_border(self) -> None:
        try:
            import ctypes

            hwnd = int(self.winId())
            dwmapi = ctypes.windll.dwmapi
            user32 = ctypes.windll.user32

            gwl_style = -16
            gwl_exstyle = -20
            ws_caption = 0x00C00000
            ws_thickframe = 0x00040000
            ws_border = 0x00800000
            ws_dlgframe = 0x00400000
            ws_ex_clientedge = 0x00000200
            ws_ex_staticedge = 0x00020000
            ws_ex_windowedge = 0x00000100
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            swp_nozorder = 0x0004
            swp_framechanged = 0x0020

            style = user32.GetWindowLongW(hwnd, gwl_style)
            style &= ~(ws_caption | ws_thickframe | ws_border | ws_dlgframe)
            user32.SetWindowLongW(hwnd, gwl_style, style)

            exstyle = user32.GetWindowLongW(hwnd, gwl_exstyle)
            exstyle &= ~(ws_ex_clientedge | ws_ex_staticedge | ws_ex_windowedge)
            user32.SetWindowLongW(hwnd, gwl_exstyle, exstyle)
            user32.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                swp_nomove | swp_nosize | swp_nozorder | swp_framechanged,
            )

            color_none = ctypes.c_uint(0xFFFFFFFE)
            for attribute in (34, 35, 36):
                dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(color_none),
                    ctypes.sizeof(color_none),
                )
        except Exception:
            return

    def _setup_timers(self) -> None:
        self.observer_timer = QTimer(self)
        self.observer_timer.timeout.connect(self._observe_low_frequency)
        self.observer_timer.start(self.settings.observer_interval_ms)

        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self._hide_bubble)

        self.idle_state_timer = QTimer(self)
        self.idle_state_timer.timeout.connect(self._apply_time_idle_state)
        self.idle_state_timer.start(self.settings.idle_state_interval_ms)

        self.roam_timer = QTimer(self)
        self.roam_timer.timeout.connect(self._idle_roam_step)
        self.roam_timer.start(12_000)

        self.drag_restore_timer = QTimer(self)
        self.drag_restore_timer.setSingleShot(True)
        self.drag_restore_timer.timeout.connect(self._end_drag)

        self.voice_limit_timer = QTimer(self)
        self.voice_limit_timer.setSingleShot(True)
        self.voice_limit_timer.timeout.connect(self._stop_voice_input)

        self.reply_wait_timer = QTimer(self)
        self.reply_wait_timer.setSingleShot(True)
        self.reply_wait_timer.timeout.connect(self._show_slow_reply)

        self.gaze_timer = QTimer(self)
        self.gaze_timer.timeout.connect(self._update_gaze)
        self.gaze_timer.start(100)

        QTimer.singleShot(1200, self._apply_time_idle_state)
        QTimer.singleShot(2200, self._startup_greeting)

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        menu = QMenu()
        show_action = menu.addAction("显示暖暖")
        pause_action = menu.addAction("暂停/恢复主动关怀")
        settings_action = menu.addAction("设置")
        memory_action = menu.addAction("记忆管理")
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        show_action.triggered.connect(self.showNormal)
        pause_action.triggered.connect(self._toggle_proactive)
        settings_action.triggered.connect(self._open_settings)
        memory_action.triggered.connect(self._open_memory)
        quit_action.triggered.connect(QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def enterEvent(self, event) -> None:
        self._update_hover_state(event.position().toPoint())
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.hover_prompt.hide()
        # Do not replace the listening/thinking/reply display deadline with
        # the short hover-dismiss timeout when the pointer leaves the pet.
        if not self.input_line.hasFocus() and not self.busy and not self.bubble_timer.isActive():
            self.bubble_timer.start(1800)
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self.bubble.isVisible() and not self.busy:
            self._hide_bubble()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            event.accept()
            return
        if (
            event.key() == Qt.Key.Key_Space
            and self.hovered
            and not self.voice_key_active
            and not self.input_line.hasFocus()
        ):
            self.voice_key_active = True
            self._toggle_voice_input()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and self.voice_key_active:
            self.voice_key_active = False
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_pos = event.globalPosition().toPoint()
            self.drag_offset = self.press_pos - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not event.buttons():
            self._update_hover_state(event.position().toPoint())
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self.press_pos
            and not self.dragging
            and (event.globalPosition().toPoint() - self.press_pos).manhattanLength() >= 8
        ):
            self._begin_drag()
            if self.windowHandle():
                self.windowHandle().startSystemMove()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        clicked_pet = (
            event.button() == Qt.MouseButton.LeftButton
            and self.press_pos is not None
            and not self.dragging
            and (event.globalPosition().toPoint() - self.press_pos).manhattanLength() < 8
            and self._pet_hit_rect().contains(event.position().toPoint())
        )
        self.drag_offset = None
        self.press_pos = None
        if self.dragging:
            self.drag_restore_timer.start(140)
        elif clicked_pet:
            self._open_chat()
        super().mouseReleaseEvent(event)

    @staticmethod
    def _pet_hit_rect() -> QRect:
        return QRect(16, 166, 398, 494)

    def _update_hover_state(self, position: QPoint) -> None:
        self.hovered = self._pet_hit_rect().contains(position)
        if self.hovered and not self.busy and not self.dragging and not self.bubble.isVisible():
            self._show_hover_prompt()
        elif not self.hovered:
            self.hover_prompt.hide()

    def _show_hover_prompt(self) -> None:
        self.hover_prompt.show()
        self.hover_prompt.raise_()

    def _open_chat(self) -> None:
        if self.dragging:
            return
        self._show_bubble()

    def _begin_drag(self) -> None:
        self.dragging = True
        self.hover_prompt.hide()
        self.live2d.set_pointer_enabled(False)
        self.animation.request(
            AnimationState.DRAGGING,
            "awkward",
            "motion_dragging",
            force=True,
        )
        self.drag_restore_timer.start(1800)

    def _end_drag(self) -> None:
        self.dragging = False
        self.live2d.show()
        self.live2d.raise_()
        self.bubble.raise_()
        self.live2d.set_pointer_enabled(True)
        self.live2d.refresh_viewport()
        self.animation.release(AnimationState.DRAGGING)

    def contextMenuEvent(self, event) -> None:
        self._show_menu(event.globalPos())
        event.accept()

    def _show_menu(self, pos: QPoint) -> None:
        if self._companion_menu is None:
            live2d_debugger = self._open_live2d_debugger if hasattr(self.live2d, "get_parameters") else None
            self._companion_menu = CompanionMenu(
                parent=self,
                open_settings=self._open_settings,
                open_memory=self._open_memory,
                analyze_screen=self._visual_refresh,
                like_reminder=self._like_last_reminder,
                reduce_reminder=self._reduce_last_reminder,
                preview_expression=self._preview_expression,
                open_live2d_debugger=live2d_debugger,
                quit_app=QApplication.quit,
            )
        self._companion_menu.show_at(pos)

    def _preview_expression(self, expression: str) -> None:
        self._display_text(f"表情测试：{expression}", expression, "motion_idle")

    def _open_settings(self) -> None:
        before_preferences = self.preferences.load()
        dialog = SettingsDialog(self.preferences, self)
        if dialog.exec():
            if dialog.preferences.speech_mode == "off":
                self.tts_service.stop()
            if dialog.preferences.renderer_backend != before_preferences.renderer_backend:
                self._display_text("渲染器已保存，重新启动暖暖后生效呀。", "wink", "motion_idle")

    def _open_memory(self) -> None:
        MemoryDialog(self.persona_agent.long_memory, self).exec()

    def _toggle_proactive(self) -> None:
        current = self.preferences.load()
        updated = self.preferences.update(proactive_enabled=not current.proactive_enabled)
        message = "主动关怀已开启。" if updated.proactive_enabled else "主动关怀已暂停。"
        self._display_text(message, "wink", "motion_idle")

    def _like_last_reminder(self) -> None:
        if not self._last_proactive_reason:
            self._display_text("还没有可评价的主动提醒呀。", "wink", "motion_idle")
            return
        self.persona_agent.long_memory.add_memory(
            f"用户喜欢 {self._last_proactive_reason} 类型的主动提醒", "positive", "feedback"
        )
        self._display_text("记住啦，以后我会保持这样的关心呀。", "love", "motion_shy")

    def _reduce_last_reminder(self) -> None:
        mapping = {
            "morning_greeting": "trigger_greeting_enabled",
            "late_night": "trigger_late_night_enabled",
            "long_coding": "trigger_coding_enabled",
            "relaxing": "trigger_relaxing_enabled",
            "craft_fashion_interest": "trigger_interest_enabled",
            "high_place": "trigger_position_enabled",
            "casual_checkin": "trigger_casual_enabled",
        }
        field = mapping.get(self._last_proactive_reason or "")
        if not field:
            self._display_text("还没有可调整的主动提醒呀。", "wink", "motion_idle")
            return
        self.preferences.update(**{field: False})
        self._display_text("好的，这一类提醒已经关闭了。", "wink", "motion_idle")

    def _open_live2d_debugger(self) -> None:
        if hasattr(self.live2d, "get_parameters"):
            Live2DParameterDialog(self.live2d, self).exec()

    def _display_live2d_log(self, message: str) -> None:
        print(f"[Live2D] {message}")

    def _startup_greeting(self) -> None:
        if self.busy or self.dragging:
            return
        context = self._window_context()
        context["topic"] = "开机问候"
        context["time_state"] = self._current_idle_state()
        self._run_agent(
            AgentTask(
                "系统刚启动，暖暖根据当前时间向用户做一句自然的开机问候。",
                context,
                proactive=True,
            ),
            thinking_text="暖暖正在醒来呀...",
        )

    def _current_idle_state(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 10:
            return "morning"
        if 10 <= hour < 18:
            return "day"
        if 18 <= hour < 23:
            return "evening"
        return "night"

    def _apply_time_idle_state(self) -> None:
        if self.dragging:
            return
        if hasattr(self.live2d, "set_idle_state"):
            self.live2d.set_idle_state(self._current_idle_state())
        elif not self.busy:
            state = AnimationState.SLEEPING if self._current_idle_state() == "night" else AnimationState.IDLE
            self.animation.request(state, "wink", "motion_idle", force=True)

    def _idle_roam_step(self) -> None:
        if self.busy or self.dragging or self.bubble.isVisible():
            return
        screen = QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        target_y = max(available.top(), available.bottom() - self.height() + 12)
        step = 36 * self.roam_direction
        next_x = self.x() + step
        left = available.left()
        right = available.right() - self.width()
        if next_x <= left or next_x >= right:
            self.roam_direction *= -1
            next_x = max(left, min(right, self.x() + 36 * self.roam_direction))
        roam_state = AnimationState.ROAM_LEFT if self.roam_direction < 0 else AnimationState.ROAM_RIGHT
        self.animation.request(roam_state, "wink", "motion_idle", duration_ms=1500)
        self.move(next_x, target_y)

    def _update_gaze(self) -> None:
        if not hasattr(self.live2d, "set_look_vector") or self.dragging:
            return
        local = self.mapFromGlobal(QCursor.pos())
        x = max(-1.0, min(1.0, (local.x() / max(1, self.width())) * 2 - 1))
        y = max(-1.0, min(1.0, 1 - (local.y() / max(1, self.height())) * 2))
        self.live2d.set_look_vector(x, y)

    def _submit_user_text(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        if self.busy:
            self._pending_user_text = text
            self._show_thinking("收到啦，暖暖回复完上一条就来看这句呀...", "wink", "motion_idle")
            return
        context = self._window_context()
        self._run_agent(AgentTask(text, context, proactive=False))

    def _toggle_voice_input(self) -> None:
        if self.recording_voice:
            self._stop_voice_input()
        else:
            self._start_voice_input()

    def _start_voice_input(self) -> None:
        if self.busy:
            return
        self._cancel_speech()
        try:
            self.asr_service.start_recording()
        except Exception as exc:
            print(f"[ASR] start failed: {exc}")
            self._display_text("唔，麦克风没有打开。请允许 python.exe 使用麦克风后再试一次呀。", "awkward", "motion_idle")
            return
        self.recording_voice = True
        self.busy = True
        self.input_line.setEnabled(False)
        self.say_button.setEnabled(False)
        self.voice_button.setEnabled(True)
        self.voice_button.setIcon(qta.icon("fa6s.stop", color="#ffffff"))
        self.voice_button.setToolTip("结束录音")
        self.voice_button.setAccessibleName("结束录音")
        self.voice_limit_timer.start(self.settings.asr_max_record_seconds * 1000)
        self._show_thinking("暖暖正在听晓灵说话呀，录好后再点一次结束录音。", "rose", "motion_listen")

    def _stop_voice_input(self) -> None:
        if not self.recording_voice:
            return
        self.voice_limit_timer.stop()
        self._show_thinking("暖暖正在整理刚刚听到的话呀...", "dizzy", "motion_think")
        self.voice_button.setEnabled(False)
        worker = ASRTranscribeWorker(self.asr_service)
        worker.signals.finished.connect(self._handle_asr_result)
        self.thread_pool.start(worker)

    def _handle_asr_result(self, result: dict) -> None:
        self.recording_voice = False
        self.voice_button.setIcon(qta.icon("fa6s.microphone", color="#ffffff"))
        self.voice_button.setToolTip("语音输入")
        self.voice_button.setAccessibleName("语音输入")
        text = str(result.get("text", "")).strip()
        if not text:
            self._set_busy(False)
            self._display_text("唔，暖暖没有听清，可以再说一次吗？", "awkward", "motion_idle")
            return
        if "不可用" in text or "没听清" in text:
            self._set_busy(False)
            self._display_text(text, "awkward", "motion_idle")
            return
        self.input_line.setText(text)
        context = self._window_context()
        self.input_line.clear()
        self._set_busy(False)
        self._run_agent(AgentTask(text, context, proactive=False), thinking_text="暖暖正在思考中呀...")

    def _observe_low_frequency(self) -> None:
        if (
            self.busy
            or self._pending_user_text
            or self.input_line.hasFocus()
            or self.bubble_timer.isActive()
            or (
                self._last_user_reply_at is not None
                and (datetime.now() - self._last_user_reply_at).total_seconds()
                < self.settings.reply_visible_seconds
            )
        ):
            return
        context = self._window_context()
        trigger = self.observer_agent.evaluate(context)
        if not trigger:
            return
        context.update(trigger.get("context_patch", {}))
        context["trigger_reason"] = trigger.get("reason", "")
        self._last_proactive_reason = str(trigger.get("reason", ""))
        self._run_agent(
            AgentTask(trigger["message"], context, proactive=True),
            thinking_text="暖暖正在想怎么开口呀...",
        )

    def _visual_refresh(self) -> None:
        if self.busy:
            return
        self._cancel_speech()
        approved_path = self.context_builder.capture_for_preview()
        if approved_path:
            prompt = QMessageBox(self)
            prompt.setWindowTitle("截图发送预览")
            prompt.setText("仅当你确认后，这张截图才会发给视觉模型；调用结束后立即删除。")
            preview = QPixmap(str(approved_path)).scaled(
                520,
                300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            prompt.setIconPixmap(preview)
            prompt.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if prompt.exec() != QMessageBox.StandardButton.Yes:
                approved_path.unlink(missing_ok=True)
                return
        self._set_busy(True)
        self._show_thinking("暖暖正在看屏幕中呀...", "dizzy", "motion_tilt_head")
        worker = VisualAgentWorker(
            self.context_builder,
            self.persona_agent,
            "请根据刚刚看到的屏幕内容判断晓灵在做什么，并做出相对应的自然反应。",
            proactive=False,
            approved_image_path=approved_path,
        )
        worker.signals.finished.connect(self._handle_agent_result)
        self.thread_pool.start(worker)

    def _run_agent(self, task: AgentTask, thinking_text: str = "暖暖正在思考中呀...") -> None:
        if self.busy:
            if not task.proactive:
                self._pending_user_text = task.user_text
            return
        self._active_task_proactive = task.proactive
        self._cancel_speech()
        self._set_busy(True)
        self._show_thinking(thinking_text, "dizzy", "motion_tilt_head")
        self.reply_wait_timer.start(4500)
        worker = AgentWorker(self.persona_agent, task)
        worker.signals.finished.connect(self._handle_agent_result)
        self.thread_pool.start(worker)

    def _handle_agent_result(self, result: dict) -> None:
        self.reply_wait_timer.stop()
        proactive = bool(result.get("_reply_meta", {}).get("proactive", self._active_task_proactive))
        if proactive and self._pending_user_text:
            self._set_busy(False)
            self._active_task_proactive = False
            self._run_pending_user_message()
            return
        response = result.get("response", {})
        mapped = self.actions.map(
            response.get("emotion", "wink"),
            response.get("action", "motion_idle"),
        )
        print(
            "[Agent]",
            f"emotion={response.get('emotion', 'wink')}",
            f"state={mapped.state.value}",
            f"action={mapped.action}",
            f"text={response.get('text', '')[:80]}",
        )
        reply_text = str(response.get("text", "暖暖在这里呀。"))
        self._display_text(
            reply_text,
            mapped.emotion,
            mapped.action,
        )
        self._set_busy(False)
        if not proactive:
            self._last_user_reply_at = datetime.now()
            self._speak_reply(reply_text)
        self._active_task_proactive = False
        self._run_pending_user_message()

    def _show_slow_reply(self) -> None:
        if self.busy:
            self._show_thinking("网络有点慢，暖暖还在认真思考，没有丢掉你的消息呀...", "dizzy", "motion_think")

    def _run_pending_user_message(self) -> None:
        text = self._pending_user_text
        if not text:
            return
        self._pending_user_text = None
        context = self._window_context()
        QTimer.singleShot(0, lambda: self._run_agent(AgentTask(text, context, proactive=False)))

    def _speak_reply(self, text: str) -> None:
        mode = self.tts_service.mode
        if mode == "off":
            return
        self._tts_request_id += 1
        request_id = self._tts_request_id
        if mode == "system":
            self.tts_service.speak_system(text)
            return
        worker = TTSWorker(self.tts_service, text)
        worker.signals.finished.connect(
            lambda result, current=request_id, reply=text: self._handle_tts_result(current, reply, result)
        )
        self.thread_pool.start(worker)

    def _handle_tts_result(self, request_id: int, text: str, result: dict) -> None:
        audio_path = Path(str(result.get("audio_path", ""))) if result.get("audio_path") else None
        if request_id != self._tts_request_id:
            if audio_path:
                audio_path.unlink(missing_ok=True)
            return
        self.tts_service.play_online_or_fallback(text, audio_path)

    def _cancel_speech(self) -> None:
        self._tts_request_id += 1
        self.tts_service.stop()

    def _display_text(self, text: str, expression: str, action: str) -> None:
        mapped = self.actions.map(expression, action)
        self.animation.request(
            mapped.state,
            mapped.emotion,
            mapped.action,
            duration_ms=2600,
            force=True,
        )
        self.speech_label.setText(text)
        self.input_line.setPlaceholderText("回复暖暖...")
        self._show_bubble()
        self.bubble_timer.start(self.settings.reply_visible_seconds * 1000)

    def _show_bubble(self) -> None:
        # A previous hover/reply timeout must never hide a newly displayed
        # listening, thinking, or final-response bubble.
        self.bubble_timer.stop()
        self.hover_prompt.hide()
        self.bubble.show()
        self.bubble.raise_()
        self.input_line.setFocus(Qt.FocusReason.MouseFocusReason)

    def _hide_bubble(self) -> None:
        self.bubble.hide()
        self.input_line.clearFocus()
        if self.hovered and not self.busy and not self.dragging:
            self._show_hover_prompt()

    def _show_thinking(self, text: str, expression: str, action: str) -> None:
        mapped = self.actions.map(expression, action)
        self.animation.request(
            mapped.state,
            mapped.emotion,
            mapped.action,
            force=True,
        )
        self.speech_label.setText(text)
        self.input_line.setPlaceholderText("暖暖马上回来...")
        self._show_bubble()
        self.bubble_timer.stop()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.input_line.setEnabled(not busy)
        self.say_button.setEnabled(not busy)
        self.voice_button.setEnabled(not busy)
        if not busy and self.animation.current in {
            AnimationState.THINKING,
            AnimationState.LISTENING,
            AnimationState.VISUAL_REVIEW,
        }:
            self.animation.force_idle()

    def _window_context(self) -> dict:
        context = self.context_builder.build_low_frequency_context()
        context["pet_window_x"] = self.x()
        context["pet_window_y"] = self.y()
        return context

    def nativeEvent(self, event_type, message):
        if event_type != "windows_generic_MSG":
            return False, 0
        try:
            import ctypes
            from ctypes import wintypes

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD),
                    ("pt", wintypes.POINT),
                ]

            msg = MSG.from_address(int(message))
            wm_nchittest = 0x0084
            httransparent = -1
            if msg.message == wm_nchittest:
                global_pos = QCursor.pos()
                local = self.mapFromGlobal(global_pos)
                interactive = QRect(35, 70, 360, 560).contains(local) or self.bubble.geometry().contains(local)
                if not interactive:
                    return True, httransparent
        except Exception:
            return False, 0
        return False, 0

    def closeEvent(self, event) -> None:
        self._cancel_speech()
        preferences = self.preferences.load()
        if preferences.remember_window_position:
            self.preferences.update(window_x=self.x(), window_y=self.y())
        super().closeEvent(event)
