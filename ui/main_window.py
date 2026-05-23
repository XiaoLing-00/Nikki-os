from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QObject, QPoint, QRect, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QWidget,
)

from agents.observer_agent import ObserverAgent
from agents.persona_agent import PersonaAgent
from config.settings import Settings
from perception.context_builder import ContextBuilder
from services.asr_service import ASRService
from ui.action_controller import ActionController
from ui.speech_bubble import SpeechBubble
from ui.sprite_pet_widget import SpritePetWidget


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
        try:
            result = self.agent.reply(
                self.task.user_text,
                self.task.context,
                proactive=self.task.proactive,
            )
        except Exception as exc:
            print(f"[Agent] worker failed: {exc}")
            result = {
                "response": {
                    "text": "刚刚思考卡住了，不过暖暖还在 00 旁边。",
                    "emotion": "awkward",
                    "action": "motion_idle",
                }
            }
        self.signals.finished.emit(result)


class VisualAgentWorker(QRunnable):
    def __init__(
        self,
        context_builder: ContextBuilder,
        agent: PersonaAgent,
        user_text: str,
        proactive: bool = False,
    ) -> None:
        super().__init__()
        self.context_builder = context_builder
        self.agent = agent
        self.user_text = user_text
        self.proactive = proactive
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            context = self.context_builder.build_visual_context()
            result = self.agent.reply(self.user_text, context, proactive=self.proactive)
        except Exception as exc:
            print(f"[Agent] visual worker failed: {exc}")
            result = {
                "response": {
                    "text": "暖暖刚刚看屏幕时卡住了，但没有保存截图。",
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
    ) -> None:
        super().__init__()
        self.settings = settings
        self.context_builder = context_builder
        self.observer_agent = observer_agent
        self.persona_agent = persona_agent
        self.asr_service = asr_service
        self.actions = ActionController()
        self.thread_pool = QThreadPool.globalInstance()
        self.drag_offset: QPoint | None = None
        self.press_pos: QPoint | None = None
        self.busy = False
        self.dragging = False
        self.recording_voice = False
        self.hovered = False
        self.voice_key_active = False
        self.roam_direction = -1
        self.last_drag_x = 0
        self.active_workers: list[tuple[int, QRunnable]] = []
        self.worker_sequence = 0
        self.current_worker_token: int | None = None

        self._setup_window()
        self._setup_ui()
        self._setup_timers()

    def _setup_window(self) -> None:
        self.setWindowTitle("苏暖暖")
        self.resize(240, 300)
        self.move(QApplication.primaryScreen().availableGeometry().right() - 280, 260)
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
        self.pet = SpritePetWidget(
            self.settings.pet_spritesheet_path,
            self.settings.pet_actions_path,
            self,
        )
        self.pet.setGeometry(0, 0, self.width(), self.height())
        self.pet.show()

        self.bubble = SpeechBubble(self)
        self.bubble.submitted.connect(self._submit_user_text)
        self.bubble.voice_requested.connect(self._toggle_voice_input)
        self.bubble.menu_requested.connect(self._show_menu)
        self.setStyleSheet("MainWindow { background: transparent; border: 0; }")

    def resizeEvent(self, event) -> None:
        if hasattr(self, "pet"):
            self.pet.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def moveEvent(self, event) -> None:
        if hasattr(self, "pet") and self.dragging:
            delta_x = self.x() - self.last_drag_x
            if abs(delta_x) >= 3:
                self.pet.set_state("running-right" if delta_x > 0 else "running-left")
                self.last_drag_x = self.x()
        if hasattr(self, "bubble") and self.bubble.isVisible():
            self._show_bubble(expanded=self.bubble.expanded, focus_input=False)
        super().moveEvent(event)

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
        self.bubble_timer.timeout.connect(self._hide_bubble_if_safe)

        self.idle_state_timer = QTimer(self)
        self.idle_state_timer.timeout.connect(self._apply_time_idle_state)
        self.idle_state_timer.start(self.settings.idle_state_interval_ms)

        self.roam_timer = QTimer(self)
        self.roam_timer.timeout.connect(self._idle_roam_step)
        self.roam_timer.start(12_000)

        self.roam_restore_timer = QTimer(self)
        self.roam_restore_timer.setSingleShot(True)
        self.roam_restore_timer.timeout.connect(self._apply_time_idle_state)

        self.drag_restore_timer = QTimer(self)
        self.drag_restore_timer.setSingleShot(True)
        self.drag_restore_timer.timeout.connect(self._end_drag)

        QTimer.singleShot(1200, self._apply_time_idle_state)
        QTimer.singleShot(2200, self._startup_greeting)

    def enterEvent(self, event) -> None:
        self.hovered = True
        self._show_bubble(expanded=self.bubble.expanded if self.bubble.isVisible() else False)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self._schedule_bubble_hide(1800)
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        if (
            event.key() == Qt.Key.Key_Space
            and self.hovered
            and not self.voice_key_active
            and not self.bubble.has_input_focus()
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
        was_click = (
            event.button() == Qt.MouseButton.LeftButton
            and self.press_pos is not None
            and not self.dragging
            and (event.globalPosition().toPoint() - self.press_pos).manhattanLength() < 8
        )
        self.drag_offset = None
        self.press_pos = None
        if self.dragging:
            self.drag_restore_timer.start(140)
        elif was_click:
            self._show_bubble(expanded=True, focus_input=True)
        super().mouseReleaseEvent(event)

    def _begin_drag(self) -> None:
        self.dragging = True
        self.last_drag_x = self.x()
        self.roam_restore_timer.stop()
        self.pet.set_pointer_enabled(False)
        self.pet.set_state("waiting")
        self.drag_restore_timer.start(1800)

    def _end_drag(self) -> None:
        self.dragging = False
        self.drag_restore_timer.stop()
        self.pet.show()
        self.pet.raise_()
        self.bubble.raise_()
        self.pet.set_pointer_enabled(True)
        self.pet.refresh_viewport()
        self._apply_time_idle_state()

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
        settings.triggered.connect(lambda: self._display_text("密钥请写入项目根目录 .env 文件。", "wink", "motion_idle"))
        action_menu = menu.addMenu("测试动作")
        action_items = (
            ("idle", "待机"),
            ("waiting", "等待"),
            ("running-left", "向左移动"),
            ("running-right", "向右移动"),
            ("waving", "挥手"),
            ("jumping", "开心"),
            ("review", "观察"),
            ("reading", "看书"),
            ("thinking", "思考"),
            ("comfort", "安慰"),
            ("snack", "吃薯片"),
            ("cheer", "加油"),
            ("designer_work", "设计师工作"),
        )
        for action_id, label in action_items:
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, name=action_id, action_label=label: self._display_text(
                    f"动作测试：{action_label}", "wink", name
                )
            )
            action_menu.addAction(action)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(refresh)
        menu.addAction(settings)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(pos)

    def _display_pet_log(self, message: str) -> None:
        print(f"[Pet] {message}")

    def _startup_greeting(self) -> None:
        if self.busy or self.dragging:
            return
        context = self._window_context()
        context["topic"] = "开机问候"
        context["time_state"] = self._current_idle_state()
        self._run_agent(
            AgentTask(
                "系统刚启动，暖暖根据当前时间向 00 做一句自然的开机问候。",
                context,
                proactive=True,
            ),
            thinking_text="暖暖正在醒来...",
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
        self.pet.set_idle_state(self._current_idle_state())

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
        self.pet.set_state("running-left" if self.roam_direction < 0 else "running-right")
        self.move(next_x, target_y)
        self.roam_restore_timer.start(900)

    def _submit_user_text(self, text: str | None = None) -> None:
        text = (text if text is not None else self.bubble.text()).strip()
        if not text:
            return
        self.bubble.clear_text()
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
            self._display_text("麦克风没有打开。请允许 python.exe 使用麦克风后再试一次。", "awkward", "motion_idle")
            return
        self.recording_voice = True
        self.busy = True
        self.bubble.input_line.setEnabled(False)
        self.bubble.say_button.setEnabled(False)
        self.bubble.voice_button.setEnabled(True)
        self.bubble.set_voice_recording(True)
        self._show_thinking("暖暖正在听 00 说话，录好后再点一次结束录音。", "rose", "motion_listen")
        self._show_bubble(expanded=True, focus_input=False)

    def _stop_voice_input(self) -> None:
        self._show_thinking("暖暖正在整理刚刚听到的话...", "dizzy", "motion_think")
        self.bubble.voice_button.setEnabled(False)
        worker = ASRTranscribeWorker(self.asr_service)
        self._start_worker(worker, self._handle_asr_result, self._asr_timeout_ms())

    def _handle_asr_result(self, result: dict) -> None:
        self.recording_voice = False
        self.bubble.set_voice_recording(False)
        text = str(result.get("text", "")).strip()
        if not text:
            self._set_busy(False)
            self._display_text("暖暖没有听清，可以再说一次吗？", "awkward", "motion_idle")
            return
        if "不可用" in text or "没听清" in text:
            self._set_busy(False)
            self._display_text(text, "awkward", "motion_idle")
            return
        context = self._window_context()
        self._set_busy(False)
        self._run_agent(AgentTask(text, context, proactive=False), thinking_text="暖暖正在思考中...")

    def _observe_low_frequency(self) -> None:
        context = self._window_context()
        trigger = self.observer_agent.evaluate(context)
        if not trigger or self.busy:
            return
        context.update(trigger.get("context_patch", {}))
        self._run_agent(
            AgentTask(trigger["message"], context, proactive=True),
            thinking_text="暖暖正在想怎么开口...",
        )

    def _visual_refresh(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self._show_thinking("暖暖正在看屏幕中...", "dizzy", "motion_tilt_head")
        worker = VisualAgentWorker(
            self.context_builder,
            self.persona_agent,
            "请根据刚刚看到的屏幕内容判断 00 在做什么，并做出相对应的自然反应。",
            proactive=False,
        )
        self._start_worker(worker, self._handle_agent_result, self._agent_timeout_ms(visual=True))

    def _run_agent(self, task: AgentTask, thinking_text: str = "暖暖正在思考中...") -> None:
        if self.busy:
            return
        self._set_busy(True)
        self._show_thinking(thinking_text, "dizzy", "motion_tilt_head")
        worker = AgentWorker(self.persona_agent, task)
        self._start_worker(worker, self._handle_agent_result, self._agent_timeout_ms())

    def _start_worker(self, worker: QRunnable, on_finished, timeout_ms: int) -> None:
        self.worker_sequence += 1
        token = self.worker_sequence
        self.current_worker_token = token
        self.active_workers.append((token, worker))
        worker.signals.finished.connect(  # type: ignore[attr-defined]
            lambda result, token=token, worker=worker, on_finished=on_finished: self._finish_worker(
                token,
                worker,
                on_finished,
                result,
            )
        )
        QTimer.singleShot(timeout_ms, lambda token=token, worker=worker: self._handle_worker_timeout(token, worker))
        self.thread_pool.start(worker)

    def _finish_worker(self, token: int, worker: QRunnable, on_finished, result: dict) -> None:
        if not self._remove_worker(token, worker):
            return
        if self.current_worker_token == token:
            self.current_worker_token = None
        on_finished(result)

    def _handle_worker_timeout(self, token: int, worker: QRunnable) -> None:
        if not self._remove_worker(token, worker):
            return
        if self.current_worker_token == token:
            self.current_worker_token = None
        if isinstance(worker, ASRTranscribeWorker):
            self.recording_voice = False
            self.bubble.set_voice_recording(False)
            self._set_busy(False)
            self._display_text("00，语音识别等太久了，我们先回到文字输入。", "awkward", "waiting")
            return
        self._set_busy(False)
        self._display_text("00，这次请求等太久了，我先把界面恢复过来。可以再点我一次。", "awkward", "waiting")

    def _remove_worker(self, token: int, worker: QRunnable) -> bool:
        for index, (active_token, active_worker) in enumerate(self.active_workers):
            if active_token == token and active_worker is worker:
                self.active_workers.pop(index)
                return True
        return False

    def _agent_timeout_ms(self, visual: bool = False) -> int:
        request_count = 2 if visual else 1
        return max(15_000, self.settings.request_timeout * request_count * 1000 + 10_000)

    def _asr_timeout_ms(self) -> int:
        return max(15_000, (self.settings.request_timeout + self.settings.asr_record_seconds) * 1000 + 10_000)

    def _handle_agent_result(self, result: dict) -> None:
        response = result.get("response", {})
        expression, action = self.actions.normalize(
            response.get("emotion", "wink"),
            response.get("action", "motion_idle"),
            result.get("context", {}),
        )
        print(
            "[Agent]",
            f"emotion={response.get('emotion', 'wink')}",
            f"expression={expression}",
            f"action={action}",
            f"text={response.get('text', '')[:80]}",
        )
        self._display_text(response.get("text", "暖暖在这里。"), expression, action, result.get("context", {}))
        self._set_busy(False)

    def _display_text(self, text: str, expression: str, action: str, context: dict | None = None) -> None:
        _expression, decided_action = self.actions.normalize(expression, action, context or {})
        self.pet.speak(expression, decided_action)
        self.bubble.set_text(text)
        self.bubble.set_placeholder("回复暖暖...")
        keep_open = self.bubble.should_stay_open() or self.recording_voice
        self._show_bubble(expanded=keep_open, focus_input=keep_open and self.bubble.has_input_focus())
        self._schedule_bubble_hide(6500)

    def _show_bubble(self, expanded: bool = False, focus_input: bool = False) -> None:
        if expanded:
            self.bubble_timer.stop()
        self.bubble.show_near(self.frameGeometry(), expanded=expanded, focus_input=focus_input)

    def _schedule_bubble_hide(self, delay_ms: int) -> None:
        if self.bubble.should_stay_open() or self.recording_voice:
            self.bubble_timer.stop()
            return
        self.bubble_timer.start(delay_ms)

    def _hide_bubble_if_safe(self) -> None:
        if self.bubble.should_stay_open() or self.recording_voice:
            self.bubble_timer.stop()
            return
        self.bubble.hide()

    def _show_thinking(self, text: str, expression: str, action: str) -> None:
        context = self._window_context()
        _expression, decided_action = self.actions.normalize(expression, action, context)
        self.pet.speak(expression, decided_action)
        self.bubble.set_text(text)
        self.bubble.set_placeholder("暖暖马上回来...")
        keep_open = self.bubble.should_stay_open() or self.recording_voice
        self._show_bubble(expanded=keep_open, focus_input=keep_open and self.bubble.has_input_focus())
        self.bubble_timer.stop()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.bubble.set_controls_enabled(not busy)

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
                interactive = QRect(0, 0, self.width(), self.height()).contains(local)
                if not interactive:
                    return True, httransparent
        except Exception:
            return False, 0
        return False, 0
