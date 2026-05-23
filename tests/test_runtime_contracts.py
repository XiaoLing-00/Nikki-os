from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PyQt6.QtGui import QImageReader
from PyQt6.QtWidgets import QApplication

from agents.observer_agent import ObserverAgent
from agents.persona_agent import PersonaAgent
from config.settings import Settings
from memory.long_memory import LongMemory
from memory.short_memory import ShortMemory
from perception.scene_classifier import classify_scene
from ui.action_controller import CUSTOM_ACTIONS, ActionController
from ui.speech_bubble import SpeechBubble
from ui.sprite_pet_widget import ANIMATIONS, CELL_HEIGHT, CELL_WIDTH, SpritePetWidget


ROOT = Path(__file__).resolve().parents[1]


class FakeLongMemory:
    def __init__(self) -> None:
        self.active_seconds = 0

    def touch_app(self, app_key: str, interval_seconds: int, reset_gap_minutes: int = 5) -> int:
        self.active_seconds += interval_seconds
        return self.active_seconds


class FakeLLMService:
    def __init__(self, result: dict) -> None:
        self.result = result

    def chat_json(self, *args, **kwargs) -> dict:
        return self.result


class RuntimeContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_action_controller_maps_persona_actions_to_sprite_states(self) -> None:
        controller = ActionController()

        for emotion in ("gentle", "sad", "angry", "happy", "wink", "love", "cry", "awkward", "dizzy", "rose", "punch"):
            expression, action = controller.normalize(emotion, "motion_think", {"scene_id": "coding"})
            self.assertIsInstance(expression, str)
            self.assertTrue(action in ANIMATIONS or action in CUSTOM_ACTIONS)

    def test_action_controller_uses_scene_and_task_to_choose_sprite_action(self) -> None:
        controller = ActionController()

        self.assertEqual(controller.decide_action("wink", "motion_idle", {"scene_id": "meeting"}), "idle")
        self.assertEqual(controller.decide_action("wink", "motion_idle", {"scene_id": "game"}), "waiting")
        self.assertEqual(controller.decide_action("wink", "motion_idle", {"scene_id": "error_debug"}), "comfort")
        self.assertEqual(
            controller.decide_action(
                "gentle",
                "motion_think",
                {"scene_id": "paper_writing", "current_task": {"title": "毕业设计论文"}},
            ),
            "running",
        )
        self.assertEqual(controller.decide_action("happy", "motion_idle", {"scene_id": "coding"}), "jumping")
        self.assertEqual(controller.decide_action("wink", "motion_idle", {"scene_id": "video_relax"}), "snack")
        self.assertEqual(controller.decide_action("wink", "motion_idle", {"scene_id": "ppt_defense"}), "cheer")
        self.assertEqual(controller.decide_action("wink", "motion_dragging", {}), "waiting")

    def test_persona_prompt_advertises_pet_actions_instead_of_legacy_drag_motion(self) -> None:
        source = (ROOT / "agents/persona_agent.py").read_text(encoding="utf-8")

        action_line = source.split('"action": "', 1)[1].split('"', 1)[0]
        self.assertIn("reading", action_line)
        self.assertIn("designer_work", action_line)
        self.assertNotIn("motion_dragging", action_line)

    def test_pet_package_references_codex_spritesheet(self) -> None:
        pet_dir = ROOT / "assets/pets/nuannuan"
        manifest = json.loads((pet_dir / "pet.json").read_text(encoding="utf-8"))
        spritesheet = pet_dir / manifest["spritesheetPath"]
        action_manifest = pet_dir / "actions" / "actions.json"

        self.assertEqual(manifest["id"], "nuannuan")
        self.assertEqual(manifest["displayName"], "暖暖")
        self.assertTrue(spritesheet.exists())
        self.assertTrue(action_manifest.exists())

        reader = QImageReader(str(spritesheet))
        size = reader.size()
        self.assertEqual(size.width(), CELL_WIDTH * 8)
        self.assertEqual(size.height(), CELL_HEIGHT * 9)

        action_payload = json.loads(action_manifest.read_text(encoding="utf-8"))
        for action in CUSTOM_ACTIONS:
            self.assertIn(action, action_payload["actions"])

    def test_sprite_pet_loads_custom_actions_and_falls_back_until_strips_exist(self) -> None:
        pet_dir = ROOT / "assets/pets/nuannuan"
        widget = SpritePetWidget(
            pet_dir / "spritesheet.webp",
            pet_dir / "actions" / "actions.json",
        )
        try:
            self.assertIn("reading", widget.custom_actions)
            widget.set_state("reading")
            self.assertEqual(widget.state, "reading")
            self.assertEqual(widget._base_state_for("reading"), "review")
            self.assertFalse(widget.custom_actions["reading"].pixmap.isNull())
            self.assertEqual(widget._current_durations(), (160, 160, 180, 160, 160, 260))
        finally:
            widget.deleteLater()

    def test_sprite_pet_speak_accepts_direct_base_and_custom_action_states(self) -> None:
        pet_dir = ROOT / "assets/pets/nuannuan"
        widget = SpritePetWidget(
            pet_dir / "spritesheet.webp",
            pet_dir / "actions" / "actions.json",
        )
        try:
            for action in ("waiting", "running-left", "running-right", "review", "reading", "thinking"):
                with self.subTest(action=action):
                    widget.speak("wink", action)
                    self.assertEqual(widget.state, action)
        finally:
            widget.deleteLater()

    def test_generated_custom_action_strips_have_expected_dimensions(self) -> None:
        actions_dir = ROOT / "assets/pets/nuannuan/actions"

        for action in ("reading", "thinking", "comfort", "snack"):
            reader = QImageReader(str(actions_dir / f"{action}.webp"))
            size = reader.size()
            self.assertEqual(size.width(), CELL_WIDTH * 6)
            self.assertEqual(size.height(), CELL_HEIGHT)

    def test_observer_triggers_long_coding_after_threshold(self) -> None:
        settings = Settings(observer_interval_ms=60_000, coding_minutes_threshold=2)
        memory = FakeLongMemory()
        observer = ObserverAgent(settings, memory)  # type: ignore[arg-type]
        observer._triggered.add(f"late_night_{datetime.now().date()}")
        observer._triggered.add(f"morning_{datetime.now().date()}")

        self.assertIsNone(observer.evaluate({"app": "VS Code"}))
        trigger = observer.evaluate({"app": "VS Code"})

        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["reason"], "long_work")

    def test_scene_classifier_covers_core_desktop_scenes(self) -> None:
        cases = [
            ({"app": "VS Code", "process_name": "Code.exe", "window_title": "main.py - Visual Studio Code"}, "coding"),
            ({"app": "Word", "process_name": "WINWORD.EXE", "window_title": "毕业设计论文.docx - Word"}, "paper_writing"),
            ({"app": "PowerPoint", "process_name": "POWERPNT.EXE", "window_title": "答辩.pptx - PowerPoint"}, "ppt_defense"),
            ({"app": "Browser", "process_name": "msedge.exe", "window_title": "ChatGPT - Edge"}, "ai_chat"),
            ({"app": "Browser", "process_name": "msedge.exe", "window_title": "Traceback exception - Edge"}, "error_debug"),
            ({"app": "Bilibili", "process_name": "chrome.exe", "window_title": "哔哩哔哩 - Chrome"}, "video_relax"),
            ({"app": "Unknown", "process_name": "DingTalk.exe", "window_title": "钉钉会议"}, "meeting"),
            ({"app": "Unknown", "process_name": "steam.exe", "window_title": "Steam"}, "game"),
        ]

        for context, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_scene(context)["id"], expected)

    def test_observer_keeps_meeting_and_game_silent(self) -> None:
        settings = Settings()
        memory = FakeLongMemory()
        observer = ObserverAgent(settings, memory)  # type: ignore[arg-type]

        for scene_id in ("meeting", "game"):
            trigger = observer.evaluate(
                {
                    "app": "Unknown",
                    "scene_id": scene_id,
                    "scene": {"id": scene_id, "name": scene_id, "proactive_level": "silent"},
                }
            )
            self.assertIsNone(trigger)

    def test_observer_includes_current_task_for_long_work_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(observer_interval_ms=60_000, coding_minutes_threshold=1)
            memory = LongMemory(Path(tmpdir) / "memory.sqlite3")
            memory.upsert_task("重做场景识别与动作系统", subtask="完善记忆库", priority="urgent")
            observer = ObserverAgent(settings, memory)
            observer._triggered.add(f"late_night_{datetime.now().date()}")
            observer._triggered.add(f"morning_{datetime.now().date()}")

            trigger = observer.evaluate(
                {
                    "app": "VS Code",
                    "scene_id": "coding",
                    "scene": {"id": "coding", "name": "写代码", "proactive_level": "medium"},
                }
            )

            self.assertIsNotNone(trigger)
            self.assertEqual(trigger["context_patch"]["current_task"]["subtask"], "完善记忆库")

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

    def test_memory_tracks_tasks_daily_state_emotion_and_repeated_long_term_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LongMemory(Path(tmpdir) / "memory.sqlite3")
            memory.upsert_task(
                "重做场景识别与动作系统",
                project="毕业设计桌宠",
                chapter="系统设计",
                subtask="完善记忆库",
                priority="urgent",
            )
            memory.upsert_task("整理 README", priority="normal")
            memory.add_daily_state("current_focus", "完善记忆库")
            memory.add_emotional_pattern("最近容易因毕设进度焦虑", intensity=1.4)

            self.assertEqual(memory.current_task()["title"], "重做场景识别与动作系统")
            self.assertEqual(memory.today_state()["current_focus"], "完善记忆库")
            self.assertEqual(memory.emotional_patterns(1)[0]["label"], "最近容易因毕设进度焦虑")

            for _ in range(2):
                memory.add_memory("00 喜欢温柔直接的提醒", "positive", "dialogue", require_repetition=True)
            self.assertEqual(memory.recent_memories(limit=1), [])
            memory.add_memory("00 喜欢温柔直接的提醒", "positive", "dialogue", require_repetition=True)
            self.assertEqual(memory.recent_memories(limit=1)[0]["key_info"], "00 喜欢温柔直接的提醒")

    def test_persona_writes_task_daily_and_emotion_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LongMemory(Path(tmpdir) / "memory.sqlite3")
            llm = FakeLLMService(
                {
                    "response": {
                        "text": "我们先把记忆库这一小段接上。",
                        "emotion": "gentle",
                        "action": "motion_think",
                    },
                    "memory_update": {"key_info": "", "sentiment": "neutral"},
                    "task_update": {
                        "title": "重做场景识别与动作系统",
                        "project": "毕业设计桌宠",
                        "chapter": "系统设计",
                        "subtask": "完善记忆库",
                        "priority": "urgent",
                        "status": "in_progress",
                    },
                    "daily_update": {"key": "current_focus", "value": "完善记忆库"},
                    "emotion_update": {"label": "最近对毕设进度很在意", "intensity": 1.0},
                }
            )
            agent = PersonaAgent(llm, ShortMemory(), memory)  # type: ignore[arg-type]

            result = agent.reply("继续做记忆库", {"app": "VS Code"})

            self.assertIn("00", result["response"]["text"])
            self.assertEqual(memory.current_task()["subtask"], "完善记忆库")
            self.assertEqual(memory.today_state()["current_focus"], "完善记忆库")
            self.assertEqual(memory.emotional_patterns(1)[0]["label"], "最近对毕设进度很在意")

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
        self.assertNotIn("self.pet.speak(\"awkward\", \"motion_dragging\")", source)
        self.assertIn("running-left", source)
        self.assertIn("running-right", source)

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

    def test_ui_keeps_worker_references_and_recovers_from_worker_timeout(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("self.active_workers", source)
        self.assertIn("def _start_worker", source)
        self.assertIn("def _handle_worker_timeout", source)
        self.assertIn("def _remove_worker", source)
        self.assertIn("QTimer.singleShot(timeout_ms", source)
        self.assertIn("self._set_busy(False)", source)
        self.assertNotIn("worker.signals.finished.connect(self._handle_agent_result)", source)
        self.assertNotIn("worker.signals.finished.connect(self._handle_asr_result)", source)

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
        self.assertIn("self.bubble_timer.timeout.connect(self._hide_bubble_if_safe)", source)
        self.assertIn("def _schedule_bubble_hide", source)
        self.assertIn("def should_stay_open", bubble_source)
        self.assertNotIn("self.bubble_timer.timeout.connect(self.bubble.hide)", source)
        self.assertIn("menu_requested", bubble_source)
        self.assertIn("def _position_near", bubble_source)
        self.assertTrue(hasattr(SpeechBubble, "submitted"))

    def test_pet_menu_uses_action_tests_instead_of_legacy_expression_tests(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("测试动作", source)
        self.assertIn("动作测试", source)
        self.assertNotIn("测试表情", source)
        self.assertNotIn("表情测试", source)
        for action in ("reading", "thinking", "comfort", "snack", "designer_work"):
            self.assertIn(action, source)

    def test_visual_refresh_runs_context_building_in_background_worker(self) -> None:
        source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
        visual_refresh = source.split("def _visual_refresh", 1)[1].split("def _run_agent", 1)[0]

        self.assertIn("VisualAgentWorker", source)
        self.assertIn("self._start_worker(worker", visual_refresh)
        self.assertIn("self.thread_pool.start(worker)", source)
        self.assertNotIn("build_visual_context()", visual_refresh)

    def test_visual_context_uses_temporary_screenshot_and_deletes_it(self) -> None:
        source = (ROOT / "perception/context_builder.py").read_text(encoding="utf-8")

        self.assertIn("NamedTemporaryFile", source)
        self.assertIn("prefix=\"soulpet_screen_\"", source)
        self.assertIn("unlink(missing_ok=True)", source)
        self.assertNotIn("capture_primary_screen(self.settings.screenshot_path)", source)
        self.assertIn("classify_scene(context)", source)

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
