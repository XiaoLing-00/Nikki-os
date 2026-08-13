from __future__ import annotations

from PyQt6.QtCore import QPoint

from ui.companion_menu import CompanionMenu


def _menu(qtbot, events: list[str]) -> CompanionMenu:
    menu = CompanionMenu(
        open_settings=lambda: events.append("settings"),
        open_memory=lambda: events.append("memory"),
        analyze_screen=lambda: events.append("analyze"),
        like_reminder=lambda: events.append("like"),
        reduce_reminder=lambda: events.append("reduce"),
        preview_expression=lambda name: events.append(f"expression:{name}"),
        quit_app=lambda: events.append("quit"),
    )
    qtbot.addWidget(menu)
    return menu


def test_menu_uses_custom_companion_surface_and_compact_hierarchy(qtbot) -> None:
    events: list[str] = []
    menu = _menu(qtbot, events)

    menu.show_at(QPoint(40, 40))

    assert menu.surface.objectName() == "companionMenuSurface"
    assert menu.stack.currentWidget() is menu.main_page
    assert menu.width() < 300
    assert menu.settings_button.text() == "设置"
    assert menu.memory_button.text() == "记忆管理"
    assert menu.more_button.text() == "更多工具"
    assert menu.quit_button.text() == "退出暖暖"


def test_more_tools_stays_inside_custom_menu(qtbot) -> None:
    events: list[str] = []
    menu = _menu(qtbot, events)
    menu.show_at(QPoint(40, 40))

    menu.more_button.click()
    assert menu.stack.currentWidget() is menu.tools_page
    assert set(menu.expression_buttons) == {"wink", "love", "cry", "awkward", "dizzy", "rose", "punch"}

    menu.back_button.click()
    assert menu.stack.currentWidget() is menu.main_page


def test_menu_action_closes_popup_and_runs_callback(qtbot) -> None:
    events: list[str] = []
    menu = _menu(qtbot, events)
    menu.show_at(QPoint(40, 40))

    menu.settings_button.click()
    qtbot.waitUntil(lambda: events == ["settings"])

    assert not menu.isVisible()
