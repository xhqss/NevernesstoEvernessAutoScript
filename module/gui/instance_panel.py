"""
Multi-instance management panel using qfluentwidgets.
"""

import os
import json

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import (
    TableWidget, PushButton, FluentIcon, SubtitleLabel, MessageBox,
)

from module.i18n import tr


def _scan(config_dir='./config'):
    path = os.path.normpath(config_dir)
    if os.path.isdir(path):
        return sorted(f[:-5] for f in os.listdir(path) if f.endswith('.json'))
    return []


class InstancePanel(QWidget):
    instance_start = Signal(str)
    instance_stop = Signal(str)
    instance_restart = Signal(str)
    instance_stop_all = Signal()
    multi_launch = Signal(str, int)

    def __init__(self, config_dir='./config', parent=None):
        super().__init__(parent)
        self._config_dir = config_dir
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(SubtitleLabel(tr('Multi-Instance Manager')))

        self._table = TableWidget(self)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([tr('Config Name'), tr('Status'), tr('Actions')])
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.verticalHeader().hide()
        layout.addWidget(self._table)

        bar = QHBoxLayout()
        btn_multi = PushButton(FluentIcon.ADD, tr('Multi-Launch'))
        btn_multi.clicked.connect(lambda: self.multi_launch.emit('template', 2))
        bar.addWidget(btn_multi)
        bar.addStretch()
        btn_stop_all = PushButton(FluentIcon.CLOSE, tr('Stop All'))
        btn_stop_all.clicked.connect(lambda: self.instance_stop_all.emit())
        bar.addWidget(btn_stop_all)
        layout.addLayout(bar)

    def refresh(self):
        configs = _scan(self._config_dir)
        self._table.setRowCount(len(configs))
        for i, name in enumerate(configs):
            self._table.setItem(i, 0, name, '')
            self._table.setItem(i, 1, tr('Stopped'), '')
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(4)
            btn_start = PushButton(FluentIcon.PLAY, '')
            btn_start.setFixedWidth(40)
            btn_start.clicked.connect(lambda checked, n=name: self.instance_start.emit(n))
            l.addWidget(btn_start)
            btn_stop = PushButton(FluentIcon.PAUSE, '')
            btn_stop.setFixedWidth(40)
            btn_stop.clicked.connect(lambda checked, n=name: self.instance_stop.emit(n))
            l.addWidget(btn_stop)
            self._table.setCellWidget(i, 2, w)
        self._table.resizeColumnsToContents()

    def set_config_dir(self, path):
        self._config_dir = path
        self.refresh()
