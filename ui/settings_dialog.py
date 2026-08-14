from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.preferences import PreferencesStore
from config.settings import BASE_DIR
from memory.long_memory import LongMemory
from platforms.autostart import set_auto_start


class SettingsDialog(QDialog):
    def __init__(self, store: PreferencesStore, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.preferences = store.load()
        self.setWindowTitle("暖暖设置")
        self.resize(500, 430)
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._appearance_tab(), "外观")
        tabs.addTab(self._privacy_tab(), "隐私")
        tabs.addTab(self._proactive_tab(), "主动关怀")
        root.addWidget(tabs)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.renderer = QComboBox()
        self.renderer.addItem("序列帧（稳定、离线）", "sprite")
        self.renderer.addItem("Live2D（实验模式）", "live2d")
        self.renderer.setCurrentIndex(max(0, self.renderer.findData(self.preferences.renderer_backend)))
        form.addRow("角色渲染器", self.renderer)
        self.speech_mode = QComboBox()
        self.speech_mode.addItem("免费在线神经语音（无需密钥）", "edge")
        self.speech_mode.addItem("仅使用系统语音（离线）", "system")
        self.speech_mode.addItem("关闭语音播报", "off")
        self.speech_mode.setCurrentIndex(max(0, self.speech_mode.findData(self.preferences.speech_mode)))
        form.addRow("回复语音", self.speech_mode)
        self.speech_voice = QComboBox()
        self.speech_voice.addItem("晓晓（温柔自然女声）", "zh-CN-XiaoxiaoNeural")
        self.speech_voice.addItem("晓伊（活泼女声）", "zh-CN-XiaoyiNeural")
        self.speech_voice.addItem("云希（自然男声）", "zh-CN-YunxiNeural")
        self.speech_voice.setCurrentIndex(max(0, self.speech_voice.findData(self.preferences.speech_voice)))
        form.addRow("在线音色", self.speech_voice)
        self.speech_rate = QSpinBox()
        self.speech_rate.setRange(-20, 30)
        self.speech_rate.setSuffix("%")
        self.speech_rate.setValue(self.preferences.speech_rate)
        form.addRow("语速调整", self.speech_rate)
        self.speech_mode.currentIndexChanged.connect(self._update_speech_controls)
        self._update_speech_controls()
        self.remember_position = QCheckBox("记住桌宠位置")
        self.remember_position.setChecked(self.preferences.remember_window_position)
        form.addRow(self.remember_position)
        self.auto_start = QCheckBox("登录系统后自动启动（保存后由平台适配器应用）")
        self.auto_start.setChecked(self.preferences.auto_start)
        form.addRow(self.auto_start)
        form.addRow(QLabel("切换渲染器后需要重新启动暖暖。"))
        return page

    def _update_speech_controls(self) -> None:
        online = self.speech_mode.currentData() == "edge"
        self.speech_voice.setEnabled(online)
        self.speech_rate.setEnabled(online)

    def _privacy_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.perception = QComboBox()
        self.perception.addItem("关闭桌面感知", "off")
        self.perception.addItem("仅识别应用类型", "app_only")
        self.perception.addItem("允许读取窗口标题", "window_title")
        self.perception.setCurrentIndex(max(0, self.perception.findData(self.preferences.perception_mode)))
        form.addRow("低频感知", self.perception)
        self.vision = QCheckBox("允许右键触发截图分析（截图调用后立即删除）")
        self.vision.setChecked(self.preferences.vision_enabled)
        form.addRow(self.vision)
        self.excluded_apps = QLineEdit(", ".join(self.preferences.excluded_apps))
        self.excluded_apps.setPlaceholderText("1Password, 银行, 支付")
        form.addRow("敏感应用关键词", self.excluded_apps)
        form.addRow(QLabel("匹配敏感关键词时不会读取标题，也不会截图。"))
        return page

    def _proactive_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.proactive = QCheckBox("启用主动关怀")
        self.proactive.setChecked(self.preferences.proactive_enabled)
        form.addRow(self.proactive)
        self.quiet_start = QSpinBox()
        self.quiet_start.setRange(0, 23)
        self.quiet_start.setValue(self.preferences.quiet_start)
        self.quiet_end = QSpinBox()
        self.quiet_end.setRange(0, 23)
        self.quiet_end.setValue(self.preferences.quiet_end)
        form.addRow("安静时段开始", self.quiet_start)
        form.addRow("安静时段结束", self.quiet_end)
        self.trigger_checks: dict[str, QCheckBox] = {}
        for field, label in (
            ("trigger_greeting_enabled", "早晨问候"),
            ("trigger_late_night_enabled", "深夜休息提醒"),
            ("trigger_coding_enabled", "长时间编程提醒"),
            ("trigger_relaxing_enabled", "视频休闲陪伴"),
            ("trigger_interest_enabled", "手工/服装兴趣回应"),
            ("trigger_position_enabled", "桌宠位置回应"),
            ("trigger_casual_enabled", "偶尔短句陪伴"),
        ):
            checkbox = QCheckBox(label)
            checkbox.setChecked(bool(getattr(self.preferences, field)))
            self.trigger_checks[field] = checkbox
            form.addRow(checkbox)
        return page

    def _save(self) -> None:
        auto_start_changed = self.auto_start.isChecked() != self.preferences.auto_start
        excluded = tuple(
            item.strip() for item in self.excluded_apps.text().replace("，", ",").split(",") if item.strip()
        )
        self.preferences = replace(
            self.preferences,
            renderer_backend=str(self.renderer.currentData()),
            speech_mode=str(self.speech_mode.currentData()),
            speech_voice=str(self.speech_voice.currentData()),
            speech_rate=self.speech_rate.value(),
            perception_mode=str(self.perception.currentData()),
            vision_enabled=self.vision.isChecked(),
            proactive_enabled=self.proactive.isChecked(),
            quiet_start=self.quiet_start.value(),
            quiet_end=self.quiet_end.value(),
            excluded_apps=excluded,
            remember_window_position=self.remember_position.isChecked(),
            auto_start=self.auto_start.isChecked(),
            **{field: checkbox.isChecked() for field, checkbox in self.trigger_checks.items()},
        )
        self.store.save(self.preferences)
        if auto_start_changed:
            ok, detail = set_auto_start(self.preferences.auto_start, BASE_DIR)
            if not ok:
                QMessageBox.warning(self, "自动启动未更新", detail)
        self.accept()


class MemoryDialog(QDialog):
    def __init__(self, memory: LongMemory, parent=None) -> None:
        super().__init__(parent)
        self.memory = memory
        self.setWindowTitle("长期记忆管理")
        self.resize(760, 500)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("暖暖只保存非敏感的用户事实和偏好；你可以随时修改或删除。"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "记忆", "情绪", "来源", "时间"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        root.addWidget(self.table)
        row = QHBoxLayout()
        save = QPushButton("保存修改")
        delete = QPushButton("删除所选")
        clear = QPushButton("清空全部")
        close = QPushButton("关闭")
        save.clicked.connect(self._save_selected)
        delete.clicked.connect(self._delete_selected)
        clear.clicked.connect(self._clear_all)
        close.clicked.connect(self.accept)
        row.addWidget(save)
        row.addWidget(delete)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self._reload()

    def _reload(self) -> None:
        rows = self.memory.list_memories()
        self.table.setRowCount(len(rows))
        for row_index, memory in enumerate(rows):
            values = [memory["id"], memory["key_info"], memory["sentiment"], memory["source"], memory["created_at"]]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column != 1 and column != 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column, item)

    def _selected(self) -> int | None:
        row = self.table.currentRow()
        return int(self.table.item(row, 0).text()) if row >= 0 else None

    def _save_selected(self) -> None:
        memory_id = self._selected()
        if memory_id is None:
            return
        row = self.table.currentRow()
        ok = self.memory.update_memory(
            memory_id,
            self.table.item(row, 1).text(),
            self.table.item(row, 2).text(),
        )
        if not ok:
            QMessageBox.warning(self, "未保存", "内容为空、包含敏感信息或记录已不存在。")
        self._reload()

    def _delete_selected(self) -> None:
        memory_id = self._selected()
        if memory_id is not None:
            self.memory.delete_memory(memory_id)
            self._reload()

    def _clear_all(self) -> None:
        answer = QMessageBox.question(self, "清空记忆", "确定删除全部长期记忆吗？此操作无法撤销。")
        if answer == QMessageBox.StandardButton.Yes:
            self.memory.clear_memories()
            self._reload()
