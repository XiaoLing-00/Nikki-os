from __future__ import annotations

import sys
from argparse import ArgumentParser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from agents.observer_agent import ObserverAgent
from agents.persona_agent import PersonaAgent
from config.settings import get_settings
from memory.long_memory import LongMemory
from memory.short_memory import ShortMemory
from perception.context_builder import ContextBuilder
from services.asr_service import ASRService
from services.llm_service import LLMService
from ui.main_window import MainWindow
from utils.doctor import run_doctor


def main() -> int:
    parser = ArgumentParser(description="SoulPet-OS desktop companion")
    parser.add_argument("--doctor", action="store_true", help="run local configuration and asset diagnostics")
    parser.add_argument("--doctor-api", action="store_true", help="also ping DashScope text API")
    args = parser.parse_args()

    settings = get_settings()
    if args.doctor or args.doctor_api:
        return run_doctor(settings, check_api=args.doctor_api)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    llm_service = LLMService(settings)
    long_memory = LongMemory(settings.database_path)
    short_memory = ShortMemory(settings.short_memory_turns)
    context_builder = ContextBuilder(settings, llm_service)
    observer_agent = ObserverAgent(settings, long_memory)
    persona_agent = PersonaAgent(llm_service, short_memory, long_memory)
    asr_service = ASRService(settings)

    window = MainWindow(settings, context_builder, observer_agent, persona_agent, asr_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
