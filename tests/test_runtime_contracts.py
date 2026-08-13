from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path

from agents.observer_agent import ObserverAgent
from agents.persona_agent import PersonaAgent
from config.preferences import PreferencesStore
from config.settings import Settings, get_settings
from memory.long_memory import LongMemory
from ui.action_controller import ActionController

ROOT = Path(__file__).resolve().parents[1]


class FakeLongMemory:
    def __init__(self) -> None:
        self.active_seconds = 0

    def touch_app(self, app_key: str, interval_seconds: int, reset_gap_minutes: int = 5) -> int:
        self.active_seconds += interval_seconds
        return self.active_seconds


class RuntimeContractsTest(unittest.TestCase):
    def _unmuted_preferences(self, tmpdir: str) -> PreferencesStore:
        store = PreferencesStore(Path(tmpdir) / "preferences.json")
        store.update(quiet_start=0, quiet_end=0)
        return store

    def test_action_controller_maps_persona_emotions_to_existing_expressions(self) -> None:
        model = json.loads((ROOT / "assets/live2d/nikki/model3.json").read_text(encoding="utf-8"))
        available = {
            item["Name"]
            for item in model["FileReferences"]["Expressions"]
        }
        controller = ActionController()

        for emotion in ("gentle", "sad", "angry", "happy", "wink", "love", "cry", "awkward", "dizzy", "rose", "punch"):
            expression, _action = controller.normalize(emotion, "motion_idle")
            self.assertIn(expression, available)

    def test_live2d_model_references_resolve_and_second_texture_is_present(self) -> None:
        model_path = ROOT / "assets/live2d/nikki/model3.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        refs = model["FileReferences"]
        model_root = model_path.parent

        referenced = [refs["Moc"], refs["Physics"], *refs["Textures"]]
        referenced.extend(
            motion["File"]
            for motions in refs["Motions"].values()
            for motion in motions
        )
        referenced.extend(expression["File"] for expression in refs["Expressions"])

        missing = [item for item in referenced if not (model_root / item).exists()]
        self.assertEqual(missing, [])
        self.assertGreaterEqual(len(refs["Textures"]), 2)

    def test_observer_triggers_long_coding_after_threshold(self) -> None:
        settings = Settings(observer_interval_ms=60_000, coding_minutes_threshold=2)
        memory = FakeLongMemory()
        with tempfile.TemporaryDirectory() as tmpdir:
            observer = ObserverAgent(settings, memory, self._unmuted_preferences(tmpdir))  # type: ignore[arg-type]
            observer._triggered.add(f"late_night_{datetime.now().date()}")
            observer._triggered.add(f"morning_{datetime.now().date()}")

            self.assertIsNone(observer.evaluate({"app": "VS Code"}))
            trigger = observer.evaluate({"app": "VS Code"})

        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["reason"], "long_coding")

    def test_observer_triggers_high_place_reaction(self) -> None:
        settings = Settings()
        memory = FakeLongMemory()
        with tempfile.TemporaryDirectory() as tmpdir:
            observer = ObserverAgent(settings, memory, self._unmuted_preferences(tmpdir))  # type: ignore[arg-type]
            observer._triggered.add(f"late_night_{datetime.now().date()}")
            observer._triggered.add(f"morning_{datetime.now().date()}")

            trigger = observer.evaluate({"app": "Browser", "pet_window_y": 20})

        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["reason"], "high_place")

    def test_long_memory_contains_design_schema_and_affection_stat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LongMemory(Path(tmpdir) / "memory.sqlite3")
            memory.add_memory("晓灵喜欢服装设计资料", "positive", "dialogue")

            self.assertEqual(memory.profile()["name"], "晓灵")
            self.assertGreaterEqual(memory.stats()["affection"], 2)
            self.assertEqual(memory.recent_interactions(1)[0]["summary"], "晓灵喜欢服装设计资料")

    def test_main_window_drag_contract_starts_only_after_move_threshold(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def _begin_drag", source)
        self.assertNotIn("self.live2d.hide()", source)
        self.assertIn("def _end_drag", source)
        self.assertIn("self.live2d.show()", source)
        self.assertIn("startSystemMove()", source)
        mouse_press = source.split("def mousePressEvent", 1)[1].split("def mouseMoveEvent", 1)[0]
        self.assertNotIn("_begin_drag()", mouse_press)
        self.assertNotIn("self.move(event.globalPosition().toPoint() - self.drag_offset)", source)

    def test_demo_proactive_timers_are_not_present(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        settings = (ROOT / "config/settings.py").read_text(encoding="utf-8")

        self.assertNotIn("ambient_timer", source)
        self.assertNotIn("proactive_demo_timer", source)
        self.assertNotIn("_ambient_animation", source)
        self.assertNotIn("_proactive_demo_check", source)
        self.assertNotIn("ambient_animation_interval_ms", settings)
        self.assertNotIn("proactive_demo_interval_ms", settings)

    def test_ui_shows_thinking_state_while_workers_are_busy(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def _show_thinking", source)
        self.assertIn("暖暖正在思考中", source)
        self.assertIn("暖暖正在看屏幕中", source)
        self.assertIn("self.input_line.setEnabled(not busy)", source)
        self.assertIn("self.say_button.setEnabled(not busy)", source)
        self.assertIn("self.voice_button.setEnabled(not busy)", source)

    def test_new_bubble_cancels_an_old_hide_timer(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        show_bubble = source.split("def _show_bubble", 1)[1].split("def _show_thinking", 1)[0]

        self.assertLess(show_bubble.index("self.bubble_timer.stop()"), show_bubble.index("self.bubble.show()"))

    def test_mouse_leave_does_not_shorten_an_active_reply_timer(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        leave_event = source.split("def leaveEvent", 1)[1].split("def keyPressEvent", 1)[0]

        self.assertIn("not self.busy", leave_event)
        self.assertIn("not self.bubble_timer.isActive()", leave_event)

    def test_ui_supports_two_step_voice_menu_vision_and_idle_roaming(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def _update_hover_state", source)
        self.assertIn("self._pet_hit_rect().contains(position)", source)
        self.assertIn("def keyPressEvent", source)
        self.assertIn("Qt.Key.Key_Space", source)
        self.assertIn("def _toggle_voice_input", source)
        self.assertIn("结束录音", source)
        self.assertIn("ASRTranscribeWorker", source)
        self.assertIn("def contextMenuEvent", source)
        self.assertIn("self._show_menu(event.globalPos())", source)
        self.assertIn("CompanionMenu(", source)
        self.assertIn("analyze_screen=self._visual_refresh", source)
        self.assertIn("self.roam_timer", source)
        self.assertIn("def _idle_roam_step", source)
        self.assertIn("pet_window_y", source)

    def test_hover_is_compact_and_click_opens_full_chat(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn('self.hover_prompt.setGeometry(123, 84, 184, 48)', source)
        self.assertIn('self.hover_text_button = QPushButton("和暖暖说话")', source)
        self.assertIn('qta.icon("mdi6.comment-processing-outline"', source)
        self.assertIn("self.hover_text_button.clicked.connect(self._open_chat)", source)
        self.assertIn("self.hover_chat_button.clicked.connect(self._open_chat)", source)
        self.assertIn("elif clicked_pet:", source)
        self.assertIn("self._open_chat()", source)
        self.assertIn("Qt.Key.Key_Escape", source)
        self.assertIn("self._hide_bubble()", source)

    def test_plain_right_click_opens_menu_instead_of_triggering_vision(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        mouse_press = source.split("def mousePressEvent", 1)[1].split("def mouseMoveEvent", 1)[0]
        context_menu = source.split("def contextMenuEvent", 1)[1].split("def _show_menu", 1)[0]

        self.assertNotIn("_visual_refresh", mouse_press)
        self.assertNotIn("ControlModifier", context_menu)
        self.assertIn("self._show_menu(event.globalPos())", context_menu)
        menu_source = (ROOT / "ui/companion_menu.py").read_text(encoding="utf-8")
        self.assertIn("分析屏幕", menu_source)
        self.assertIn("会先请你确认截图", menu_source)

    def test_visual_refresh_runs_context_building_in_background_worker(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        visual_refresh = source.split("def _visual_refresh", 1)[1].split("def _run_agent", 1)[0]

        self.assertIn("VisualAgentWorker", source)
        self.assertIn("self.thread_pool.start(worker)", visual_refresh)
        self.assertNotIn("build_visual_context()", visual_refresh)

    def test_visual_context_uses_temporary_screenshot_and_deletes_it(self) -> None:
        source = (ROOT / "perception/context_builder.py").read_text(encoding="utf-8")

        self.assertIn("NamedTemporaryFile", source)
        self.assertIn("prefix=\"soulpet_screen_\"", source)
        self.assertIn("unlink(missing_ok=True)", source)
        self.assertNotIn("capture_primary_screen(self.settings.screenshot_path)", source)

    def test_asr_service_has_real_dashscope_recording_contract(self) -> None:
        source = (ROOT / "services/asr_service.py").read_text(encoding="utf-8")
        settings = (ROOT / "config/settings.py").read_text(encoding="utf-8")
        main = (ROOT / "main.py").read_text(encoding="utf-8")

        self.assertIn("class ASRService", source)
        self.assertIn("Recognition(", source)
        self.assertIn("recognition.call", source)
        self.assertIn("start_recording", source)
        self.assertIn("stop_and_transcribe", source)
        self.assertIn("get_sentence", source)
        self.assertIn("NamedTemporaryFile", source)
        self.assertIn("unlink(missing_ok=True)", source)
        self.assertIn("asr_model", settings)
        self.assertIn("base_websocket_api_url", source)
        self.assertIn("ASRService(settings)", main)

    def test_singapore_endpoint_selects_supported_asr_default(self) -> None:
        with unittest.mock.patch("config.settings.load_env_file"), unittest.mock.patch.dict(
            "os.environ",
            {"DASHSCOPE_BASE_URL": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"},
            clear=True,
        ):
            settings = get_settings()

        self.assertEqual(settings.asr_model, "fun-asr-realtime")

    def test_asr_result_releases_busy_before_sending_to_agent(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        handler = source.split("def _handle_asr_result", 1)[1].split("def _observe_low_frequency", 1)[0]

        self.assertLess(handler.index("self._set_busy(False)"), handler.rindex("self._run_agent("))

    def test_tts_is_backgrounded_and_has_a_system_fallback(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        tts = (ROOT / "services/tts_service.py").read_text(encoding="utf-8")

        self.assertIn("class TTSWorker", source)
        self.assertIn("self.thread_pool.start(worker)", source)
        self.assertIn("QTextToSpeech", tts)
        self.assertIn("edge_tts.Communicate", tts)
        self.assertIn("synthesize_online", tts)
        self.assertIn("speak_system", tts)

    def test_user_messages_are_queued_and_replies_stay_visible(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        settings = (ROOT / "config/settings.py").read_text(encoding="utf-8")

        self.assertIn("self._pending_user_text = text", source)
        self.assertIn("def _run_pending_user_message", source)
        self.assertIn("self.reply_wait_timer.start(4500)", source)
        self.assertIn("网络有点慢", source)
        self.assertIn("reply_visible_seconds", settings)
        self.assertIn("self.settings.reply_visible_seconds * 1000", source)

    def test_actions_json_contains_time_based_idle_states(self) -> None:
        actions = json.loads((ROOT / "assets/live2d/actions.json").read_text(encoding="utf-8"))
        states = actions["states"]

        for state in ("morning", "day", "evening", "night"):
            self.assertIn(state, states)
            self.assertIn("expression", states[state])
            self.assertIn("hiddenDrawables", states[state])

        self.assertGreater(len(states["day"]["hiddenDrawables"]), 0)
        self.assertEqual(states["night"]["hiddenDrawables"], [])

    def test_viewer_disables_live2d_pointer_focus_for_stable_dragging(self) -> None:
        source = (ROOT / "assets/live2d/viewer.html").read_text(encoding="utf-8")

        self.assertIn("autoHitTest: false", source)
        self.assertIn("autoFocus: false", source)
        self.assertIn("pointer-events: none", source)
        self.assertIn("refreshViewport", source)
        self.assertIn("baseWidth", source)
        self.assertIn("simulateMotion", source)
        self.assertIn("motion_comfort", source)
        self.assertIn("motion_listen", source)
        self.assertNotIn("window.innerWidth / model.width", source)

    def test_persona_never_calls_user_master(self) -> None:
        result = PersonaAgent._normalize(
            {
                "response": {
                    "text": "今天也辛苦啦。",
                    "emotion": "wink",
                    "action": "motion_idle",
                }
            },
            {},
        )

        self.assertNotIn("主人", result["response"]["text"])
        self.assertIn("晓灵", result["response"]["text"])

    def test_day_states_hide_blanket_drawables(self) -> None:
        actions = json.loads((ROOT / "assets/live2d/actions.json").read_text(encoding="utf-8"))
        for state in ("morning", "day", "evening"):
            hidden = set(actions["states"][state]["hiddenDrawables"])
            self.assertIn("ArtMesh54", hidden)
            self.assertIn("ArtMesh39", hidden)


if __name__ == "__main__":
    unittest.main()
