from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PyQt6.QtCore import QObject, QPoint, QRect, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
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
        self.signals.finished.emit(result)


class ASRTranscribeWorker(QRunnable):
    def __init__(self, asr_service: ASRService) -> None:
        super().__init__()
        self.asr_service = asr_service
        self.signals = WorkerSignals()

    def run(self) -> None:
        text = self.asr_service.stop_and_transcribe()
        self.signals.finished.emit({"text": text})


class MainWindow(QWidget):
    def __init__(
        self,
        settings: Settings,
        context_builder: ContextBuilder,
        observer_agent: ObserverAgent,
        persona_agent: PersonaAgent,
        asr_service: ASRService,
        preferences: PreferencesStore | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.context_builder = context_builder
        self.observer_agent = observer_agent
        self.persona_agent = persona_agent
        self.asr_service = asr_service
        self.preferences = preferences or PreferencesStore()
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
        self.bubble.setGeometry(22, 18, 386, 132)
        self.bubble.hide()

        layout = QVBoxLayout(self.bubble)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

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
        self.voice_button.clicked.connect(self._toggle_voice_input)
        input_row.addWidget(self.voice_button)

        self.say_button = QPushButton("发送")
        self.say_button.clicked.connect(self._submit_user_text)
        input_row.addWidget(self.say_button)
        layout.addLayout(input_row)

        self.setStyleSheet(
            """
            MainWindow { background: transparent; border: 0; }
            QWidget { font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; }
            #bubble {
                background: rgba(255, 250, 253, 236);
                border: 1px solid rgba(255, 170, 204, 180);
                border-radius: 8px;
            }
            #speech {
                color: #4a2433;
                font-size: 14px;
                line-height: 1.4;
                min-height: 38px;
            }
            QLineEdit {
                min-height: 34px;
                border: 1px solid rgba(233, 136, 177, 150);
                border-radius: 7px;
                padding: 0 10px;
                color: #4a2433;
                background: rgba(255, 255, 255, 245);
            }
            QPushButton {
                min-height: 30px;
                min-width: 54px;
                border: 0;
                border-radius: 7px;
                color: white;
                background: #e85f98;
            }
            QPushButton:hover { background: #d94f88; }
            QPushButton:disabled { background: rgba(168, 130, 150, 150); }
            #voiceButton { background: #7b8fd6; }
            #voiceButton:hover { background: #6d80c8; }
            """
        )

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
        self.bubble_timer.timeout.connect(self.bubble.hide)

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
        self.hovered = True
        self._show_bubble()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        if not self.input_line.hasFocus():
            self.bubble_timer.start(1800)
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
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
        elif event.button() == Qt.MouseButton.RightButton:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._show_menu(event.globalPosition().toPoint())
            else:
                self._visual_refresh()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
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
        self.drag_offset = None
        self.press_pos = None
        if self.dragging:
            self.drag_restore_timer.start(140)
        super().mouseReleaseEvent(event)

    def _begin_drag(self) -> None:
        self.dragging = True
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
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._show_menu(event.globalPos())
        else:
            event.accept()

    def _show_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        refresh = QAction("强制刷新", self)
        refresh.triggered.connect(self._visual_refresh)
        settings = QAction("设置", self)
        settings.triggered.connect(self._open_settings)
        memory = QAction("记忆管理", self)
        memory.triggered.connect(self._open_memory)
        like = QAction("喜欢这次提醒", self)
        like.triggered.connect(self._like_last_reminder)
        reduce = QAction("减少此类提醒", self)
        reduce.triggered.connect(self._reduce_last_reminder)
        expression_menu = menu.addMenu("测试表情")
        for expression in ("wink", "love", "cry", "awkward", "dizzy", "rose", "punch"):
            action = QAction(expression, self)
            action.triggered.connect(
                lambda _checked=False, name=expression: self._display_text(
                    f"表情测试：{name}", name, "motion_idle"
                )
            )
            expression_menu.addAction(action)
        if hasattr(self.live2d, "get_parameters"):
            live2d_debug = QAction("Live2D 参数调试器", self)
            live2d_debug.triggered.connect(self._open_live2d_debugger)
            menu.addAction(live2d_debug)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(refresh)
        menu.addAction(settings)
        menu.addAction(memory)
        menu.addAction(like)
        menu.addAction(reduce)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(pos)

    def _open_settings(self) -> None:
        before = self.preferences.load().renderer_backend
        dialog = SettingsDialog(self.preferences, self)
        if dialog.exec() and dialog.preferences.renderer_backend != before:
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
        self.voice_button.setText("结束录音")
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
        self.voice_button.setText("语音")
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
        if self.busy:
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
            return
        self._set_busy(True)
        self._show_thinking(thinking_text, "dizzy", "motion_tilt_head")
        worker = AgentWorker(self.persona_agent, task)
        worker.signals.finished.connect(self._handle_agent_result)
        self.thread_pool.start(worker)

    def _handle_agent_result(self, result: dict) -> None:
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
        self._display_text(
            response.get("text", "暖暖在这里呀。"),
            mapped.emotion,
            mapped.action,
        )
        self._set_busy(False)

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
        self.bubble_timer.start(6500)

    def _show_bubble(self) -> None:
        self.bubble.show()
        self.bubble.raise_()
        self.input_line.setFocus(Qt.FocusReason.MouseFocusReason)

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
        preferences = self.preferences.load()
        if preferences.remember_window_position:
            self.preferences.update(window_x=self.x(), window_y=self.y())
        super().closeEvent(event)
