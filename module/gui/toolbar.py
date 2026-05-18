"""
Explorer-style top toolbar for config and instance management.
Provides breadcrumb navigation, config switching, and action buttons.
"""

import os
import json
import shutil
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QPushButton,
    QFrame, QMenu, QFileDialog, QMessageBox, QInputDialog, QDialog
)


class ExplorerToolbar(QFrame):
    """Windows Explorer-style toolbar for config management."""

    config_new = Signal(str)       # new config name
    config_switch = Signal(str)    # switch to config name
    config_save = Signal(str)      # save-as config name
    config_delete = Signal(str)    # delete config name
    config_export = Signal(str)    # export config
    config_import = Signal()       # trigger import
    config_refresh = Signal()      # refresh list
    multi_instance = Signal()      # open instance panel
    open_config_dir = Signal()     # open config folder in explorer

    def __init__(self, config_name: str = 'template', config_dir: str = './config', parent=None):
        super().__init__(parent)
        self.setObjectName('toolbar')
        self._config_name = config_name
        self._config_dir = config_dir
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(8)

        # ── Left: Breadcrumb + Config Selector ──
        breadcrumb = QLabel('\U0001F4C1  我的配置 >')
        breadcrumb.setStyleSheet('font-size: 12px; color: #8888aa; padding: 4px 0;')
        main_layout.addWidget(breadcrumb)

        self._config_combo = QComboBox()
        self._config_combo.setMinimumWidth(220)
        self._config_combo.setStyleSheet(
            'QComboBox { font-size: 14px; font-weight: bold; padding: 6px 12px; }'
        )
        self._config_combo.currentTextChanged.connect(
            lambda name: self.config_switch.emit(name) if name else None
        )
        main_layout.addWidget(self._config_combo)

        # ── Center: Action Buttons ──
        btn_new = QPushButton('+ 新建')
        btn_new.setToolTip('新建配置 (空白 / 复制当前 / 多开模板)')
        btn_new.clicked.connect(self._show_new_menu)
        main_layout.addWidget(btn_new)

        btn_save_as = QPushButton('\U0001F4BE 另存为')
        btn_save_as.setToolTip('另存为新配置')
        btn_save_as.clicked.connect(self._on_save_as)
        main_layout.addWidget(btn_save_as)

        main_layout.addStretch()

        # ── Right: Icon Buttons ──
        icon_style = 'QPushButton { font-size: 18px; padding: 6px 10px; border-radius: 4px; }'

        btn_open_dir = QPushButton('\U0001F4C2')
        btn_open_dir.setToolTip('打开配置文件夹')
        btn_open_dir.setStyleSheet(icon_style)
        btn_open_dir.clicked.connect(lambda: self.open_config_dir.emit())
        main_layout.addWidget(btn_open_dir)

        btn_refresh = QPushButton('\U0001F504')
        btn_refresh.setToolTip('刷新配置列表')
        btn_refresh.setStyleSheet(icon_style)
        btn_refresh.clicked.connect(lambda: self.config_refresh.emit())
        main_layout.addWidget(btn_refresh)

        btn_multi = QPushButton('\U0001F465')
        btn_multi.setToolTip('多实例管理')
        btn_multi.setStyleSheet(icon_style)
        btn_multi.clicked.connect(lambda: self.multi_instance.emit())
        main_layout.addWidget(btn_multi)

        btn_export = QPushButton('\U0001F4E4')
        btn_export.setToolTip('导出配置 (.ntecfg)')
        btn_export.setStyleSheet(icon_style)
        btn_export.clicked.connect(lambda: self.config_export.emit(self._config_name))
        main_layout.addWidget(btn_export)

        btn_import = QPushButton('\U0001F4E5')
        btn_import.setToolTip('导入配置')
        btn_import.setStyleSheet(icon_style)
        btn_import.clicked.connect(lambda: self.config_import.emit())
        main_layout.addWidget(btn_import)

        btn_trash = QPushButton('\U0001F5D1')
        btn_trash.setToolTip('删除当前配置')
        btn_trash.setStyleSheet(icon_style + 'color: #ef4444;')
        btn_trash.clicked.connect(self._on_delete)
        main_layout.addWidget(btn_trash)

    def _refresh_config_list(self):
        """Scan config directory and populate combo box."""
        current = self._config_combo.currentText()
        self._config_combo.blockSignals(True)
        self._config_combo.clear()

        config_path = os.path.normpath(self._config_dir)
        if os.path.isdir(config_path):
            for fname in sorted(os.listdir(config_path)):
                if fname.endswith('.json'):
                    name = fname[:-5]  # strip .json
                    self._config_combo.addItem(name)

        # Restore selection
        idx = self._config_combo.findText(current)
        if idx >= 0:
            self._config_combo.setCurrentIndex(idx)
        self._config_combo.blockSignals(False)

    def set_config_list(self, names: list[str]):
        """Set config name list from external source."""
        current = self._config_combo.currentText()
        self._config_combo.blockSignals(True)
        self._config_combo.clear()
        for name in names:
            self._config_combo.addItem(name)
        idx = self._config_combo.findText(current)
        if idx >= 0:
            self._config_combo.setCurrentIndex(idx)
        self._config_combo.blockSignals(False)

    def set_current(self, config_name: str):
        self._config_name = config_name
        self._config_combo.blockSignals(True)
        idx = self._config_combo.findText(config_name)
        if idx >= 0:
            self._config_combo.setCurrentIndex(idx)
        self._config_combo.blockSignals(False)

    def _show_new_menu(self):
        menu = QMenu(self)
        blank = menu.addAction('空白创建')
        blank.triggered.connect(lambda: self._new_config('blank'))
        copy = menu.addAction('复制当前配置')
        copy.triggered.connect(lambda: self._new_config('copy'))
        multi = menu.addAction('多开模板 (N份)')
        multi.triggered.connect(lambda: self._new_config('multi'))
        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    def _new_config(self, mode: str):
        if mode == 'multi':
            n, ok = QInputDialog.getInt(self, '多开模板', '复制份数:', 2, 1, 20)
            if not ok:
                return
            for i in range(1, n + 1):
                name = f'{self._config_name}_{i:02d}'
                self.config_new.emit(name)
        else:
            name, ok = QInputDialog.getText(self, '新建配置', '配置名称:')
            if not ok or not name.strip():
                return
            name = name.strip()
            self.config_new.emit(name)

    def _on_save_as(self):
        name, ok = QInputDialog.getText(self, '另存为', '新配置名称:')
        if ok and name.strip():
            self.config_save.emit(name.strip())

    def _on_delete(self):
        ret = QMessageBox.question(
            self, '确认删除',
            f'确定要删除配置 "{self._config_name}" 吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.config_delete.emit(self._config_name)
