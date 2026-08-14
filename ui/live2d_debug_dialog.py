from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class Live2DParameterDialog(QDialog):
    def __init__(self, renderer, parent=None) -> None:
        super().__init__(parent)
        self.renderer = renderer
        self.snapshot: list[dict] = []
        self.setWindowTitle("Live2D 参数调试器")
        self.resize(720, 650)
        root = QVBoxLayout(self)
        self.status = QLabel("正在读取模型参数……")
        root.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.form = QFormLayout(self.container)
        scroll.setWidget(self.container)
        root.addWidget(scroll)
        buttons = QHBoxLayout()
        reset = QPushButton("重新读取")
        export = QPushButton("导出参数映射")
        close = QPushButton("关闭")
        reset.clicked.connect(self._load)
        export.clicked.connect(self._export)
        close.clicked.connect(self.accept)
        buttons.addWidget(reset)
        buttons.addWidget(export)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)
        self._load()

    def _load(self) -> None:
        self.renderer.get_parameters(self._populate)

    def _populate(self, parameters) -> None:
        self.snapshot = parameters if isinstance(parameters, list) else []
        while self.form.rowCount():
            self.form.removeRow(0)
        for parameter in self.snapshot:
            parameter_id = str(parameter.get("id", ""))
            minimum = float(parameter.get("minimum", -1))
            maximum = float(parameter.get("maximum", 1))
            value = float(parameter.get("value", parameter.get("defaultValue", 0)))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 1000)
            if maximum > minimum:
                slider.setValue(round((value - minimum) / (maximum - minimum) * 1000))
            label = QLabel(f"{value:.3f}  [{minimum:.2f}, {maximum:.2f}]")
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(slider, 1)
            layout.addWidget(label)

            def changed(position, pid=parameter_id, lo=minimum, hi=maximum, output=label):
                current = lo + (hi - lo) * position / 1000
                output.setText(f"{current:.3f}  [{lo:.2f}, {hi:.2f}]")
                self.renderer.set_parameter(pid, current)

            slider.valueChanged.connect(changed)
            self.form.addRow(parameter_id, row)
        self.status.setText(f"已读取 {len(self.snapshot)} 个参数。滑动后可观察对应的头、眼、嘴、头发或服装节点。")

    def _export(self) -> None:
        default = Path.cwd() / "live2d_parameter_map.json"
        path, _filter = QFileDialog.getSaveFileName(self, "导出参数映射", str(default), "JSON (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
