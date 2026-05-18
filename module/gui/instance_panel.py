"""
Multi-instance management panel.
Shows running instances, allows start/stop/restart, and multi-launch wizard.
"""

import os
import json
import time
import subprocess
import sys

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QSpinBox, QDialogButtonBox,
    QFormLayout, QMessageBox, QFrame
)

from module.i18n import tr


def _scan_configs(config_dir: str = './config') -> list[str]:
    """Scan config directory for .json config files."""
    configs = []
    path = os.path.normpath(config_dir)
    if os.path.isdir(path):
        for fname in sorted(os.listdir(path)):
            if fname.endswith('.json'):
                configs.append(fname[:-5])
    return configs


def _read_config_pid(config_dir: str, config_name: str) -> int | None:
    """Read PID from a config's runtime state file, if any."""
    runtime_file = os.path.join(config_dir, '.runtime', f'{config_name}.json')
    if os.path.exists(runtime_file):
        try:
            with open(runtime_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('pid')
        except Exception:
            pass
    return None


class MultiLaunchDialog(QDialog):
    """Wizard dialog for launching multiple instances."""

    def __init__(self, config_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('一键多开向导')
        self.setFixedSize(360, 180)
        self._config_name = config_name

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._count_spin = QSpinBox()
        self._count_spin.setRange(2, 20)
        self._count_spin.setValue(2)
        form.addRow('实例数量:', self._count_spin)

        layout.addLayout(form)

        info = QLabel(f'将复制 "{config_name}" 配置为 N 份，自动编号。')
        info.setWordWrap(True)
        info.setStyleSheet('color: #8888aa; font-size: 12px; padding: 8px 0;')
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def count(self) -> int:
        return self._count_spin.value()


class InstancePanel(QWidget):
    """Panel showing all instances and their status."""

    instance_start = Signal(str)     # config name
    instance_stop = Signal(str)      # config name
    instance_restart = Signal(str)   # config name
    instance_stop_all = Signal()
    multi_launch = Signal(str, int)  # config name, count

    def __init__(self, config_dir: str = './config', parent=None):
        super().__init__(parent)
        self._config_dir = config_dir
        self._instances: dict[str, dict] = {}  # config_name → {pid, status, started, ...}
        self._init_ui()

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(3000)  # every 3 seconds

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel('\U0001F465 多实例管理')
        title.setStyleSheet('font-size: 16px; font-weight: bold; padding: 4px 0;')
        layout.addWidget(title)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            '配置名称', '状态', 'PID', '运行时长', '操作'
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 150)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Action buttons
        btn_layout = QHBoxLayout()

        self._btn_multi = QPushButton('\U0001F680 一键多开')
        self._btn_multi.clicked.connect(self._on_multi_launch)
        btn_layout.addWidget(self._btn_multi)

        btn_layout.addStretch()

        btn_stop_all = QPushButton('⏹ 全部停止')
        btn_stop_all.setStyleSheet('color: #ef4444;')
        btn_stop_all.clicked.connect(lambda: self.instance_stop_all.emit())
        btn_layout.addWidget(btn_stop_all)

        layout.addLayout(btn_layout)

    def refresh(self):
        """Refresh instance list from config directory."""
        configs = _scan_configs(self._config_dir)
        self._table.setRowCount(0)
        for i, cfg_name in enumerate(configs):
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(cfg_name))

            # Status
            pid = _read_config_pid(self._config_dir, cfg_name)
            if pid:
                status = QTableWidgetItem('● 运行中')
                status.setForeground(Qt.green)
                self._table.setItem(i, 1, status)
                self._table.setItem(i, 2, QTableWidgetItem(str(pid)))
            else:
                status = QTableWidgetItem('○ 已停止')
                status.setForeground(Qt.gray)
                self._table.setItem(i, 1, status)
                self._table.setItem(i, 2, QTableWidgetItem('-'))
                self._table.setItem(i, 3, QTableWidgetItem('-'))

            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(4)

            if pid:
                btn_stop = QPushButton('停止')
                btn_stop.setStyleSheet('padding: 4px 10px; font-size: 11px; color: #ef4444;')
                btn_stop.clicked.connect(lambda checked, c=cfg_name: self.instance_stop.emit(c))
                action_layout.addWidget(btn_stop)

                btn_restart = QPushButton('重启')
                btn_restart.setStyleSheet('padding: 4px 10px; font-size: 11px;')
                btn_restart.clicked.connect(lambda checked, c=cfg_name: self.instance_restart.emit(c))
                action_layout.addWidget(btn_restart)
            else:
                btn_start = QPushButton('启动')
                btn_start.setStyleSheet('padding: 4px 10px; font-size: 11px; color: #22c55e;')
                btn_start.clicked.connect(lambda checked, c=cfg_name: self.instance_start.emit(c))
                action_layout.addWidget(btn_start)

            self._table.setCellWidget(i, 4, action_widget)

    def _on_multi_launch(self):
        config_name = 'template'
        dlg = MultiLaunchDialog(config_name, self)
        if dlg.exec() == QDialog.Accepted:
            self.multi_launch.emit(config_name, dlg.count())

    def set_config_dir(self, path: str):
        self._config_dir = path
        self.refresh()
