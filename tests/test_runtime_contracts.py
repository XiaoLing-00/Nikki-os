from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PyQt6.QtGui import QImageReader

from agents.observer_agent import ObserverAgent
from agents.persona_agent import PersonaAgent
from config.settings import Settings
from memory.long_memory import LongMemory
from ui.action_controller import ActionController
from ui.speech_bubble import SpeechBubble
from ui.sprite_pet_widget import ANIMATIONS, CELL_HEIGHT, CELL_WIDTH, MOTION_TO_STATE


ROOT = Path(__file__).resolve().parents[1]


class FakeLongMemory:
    def __init__(self) -> None:
        self.active_seconds = 0

    def touch_app(self, app_key: str, interval_seconds: int, reset_gap_minutes: int = 5) -> int:
        self.active_seconds += interval_seconds
        return self.active_seconds


class RuntimeContractsTest(unittest.TestCase):
    def test_action_controller_maps_persona_actions_to_sprite_states(self) -> None:
        controller = ActionController()

        for emotion in ("gentle", "sad", "angry", "happy", "wink", "love", "cry", "awkward", "dizzy", "rose", "punch"):
            expression, action = controller.normalize(emotion, "motion_think")
            self.assertIsInstance(expression, str)
            self.assertEqual(action, "motion_think")
            self.assertIn(MOTION_TO_STATE[action], ANIMATIONS)

    def test_pet_package_references_codex_spritesheet(self) -> None:
        pet_dir = ROOT / "assets/pets/nuannuan"
        manifest = json.loads((pet_dir / "pet.json").read_text(encoding="utf-8"))
        spritesheet = pet_dir / manifest["spritesheetPath"]

        self.assertEqual(manifest["id"], "nuannuan")
        self.assertEqual(manifest["displayName"], "暖暖")
        self.assertTrue(spritesheet.exists())

        reader = QImageReader(str(spritesheet))
        size = reader.size()
        self.assertEqual(size.width(), CELL_WIDTH * 8)
        self.assertEqual(size.height(), CELL_HEIGHT * 9)

    def test_observer_triggers_long_coding_after_threshold(self) -> None:
        settings = Settings(observer_interval_ms=60_000, coding_minutes_threshold=2)
        memory = FakeLongMemory()
        observer = ObserverAgent(settings, memory)  # type: ignore[arg-type]
        observer._triggered.add(f"late_night_{datetime.now().date()}")
        observer._triggered.add(f"morning_{datetime.now().date()}")

        self.assertIsNone(observer.evaluate({"app": "VS Code"}))
        trigger = observer.evaluate({"app": "VS Code"})

        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["reason"], "long_coding")

    def test_observer_triggers_high_place_reaction(self) -> None:
        settings = Settings()
        memory = FakeLongMemory()
        observer = ObserverAgent(settings, memory)  # type: ignore[arg-type]
        observer._triggered.add(f"late_night_{datetime.now().date()}")
        observer._triggered.add(f"morning_{datetime.now().date()}")

        trigger = observer.evaluate({"app": "Browser", "pet_window_y": 20})

        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["reason"], "high_place")

    def test_long_memory_contains_design_schema_and_affection_stat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LongMemory(Path(tmpdir) / "memory.sqlite3")
            memory.add_memory("00 喜欢服装设计资料", "positive", "dialogue")

            self.assertEqual(memory.profile()["name"], "00")
            self.assertGreaterEqual(memory.stats()["affection"], 2)
            self.assertEqual(memory.recent_interactions(1)[0]["summary"], "00 喜欢服装设计资料")

    def test_main_window_drag_contract_starts_only_after_move_threshold(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def _begin_drag", source)
        self.assertNotIn("self.pet.hide()", source)
        self.assertIn("def _end_drag", source)
        self.assertIn("self.pet.show()", source)
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
        self.assertIn("self.bubble.set_controls_enabled(not busy)", source)

    def test_ui_supports_two_step_voice_right_click_vision_and_idle_roaming(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("self.hovered = True", source)
        self.assertIn("def keyPressEvent", source)
        self.assertIn("Qt.Key.Key_Space", source)
        self.assertIn("def _toggle_voice_input", source)
        self.assertIn("结束录音", source)
        self.assertIn("ASRTranscribeWorker", source)
        self.assertIn("Qt.MouseButton.RightButton", source)
        self.assertIn("self._visual_refresh()", source)
        self.assertIn("self.roam_timer", source)
        self.assertIn("def _idle_roam_step", source)
        self.assertIn("pet_window_y", source)

    def test_ui_uses_detached_npc_bubble_that_expands_on_pet_click(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        bubble_source = (ROOT / "ui/speech_bubble.py").read_text(encoding="utf-8")

        self.assertIn("SpeechBubble(self)", source)
        self.assertIn("self.bubble.show_near", source)
        self.assertIn("_show_bubble(expanded=True, focus_input=True)", source)
        self.assertIn("menu_requested", bubble_source)
        self.assertIn("def _position_near", bubble_source)
        self.assertTrue(hasattr(SpeechBubble, "submitted"))

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
        self.assertIn("ASRService(settings)", main)

    def test_asr_result_releases_busy_before_sending_to_agent(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        handler = source.split("def _handle_asr_result", 1)[1].split("def _observe_low_frequency", 1)[0]

        self.assertLess(handler.index("self._set_busy(False)"), handler.rindex("self._run_agent("))

    def test_sprite_pet_supports_time_based_idle_states(self) -> None:
        source = (ROOT / "ui/sprite_pet_widget.py").read_text(encoding="utf-8")

        self.assertIn("def set_idle_state", source)
        self.assertIn("if state == \"night\"", source)
        self.assertIn("self.set_state(\"waiting\")", source)

    def test_sprite_pet_widget_defines_codex_atlas_contract(self) -> None:
        self.assertEqual(CELL_WIDTH, 192)
        self.assertEqual(CELL_HEIGHT, 208)
        for state in ("idle", "running-right", "running-left", "waving", "jumping", "failed", "waiting", "running", "review"):
            self.assertIn(state, ANIMATIONS)

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
        self.assertIn("00", result["response"]["text"])


if __name__ == "__main__":
    unittest.main()
