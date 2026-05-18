"""
Key binding table widget for game control configuration.
Displays bindings in a table with key capture support.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QLabel, QMessageBox
)

from module.gui.widgets import KeyCaptureDialog
from module.i18n import tr


# ── Key binding metadata ──

_KEY_DEFS = [
    ('SkillKey',       '技能键',     '普通攻击'),
    ('UltimateKey',    '终极技键', '释放终极技'),
    ('ArcKey',         '奥义键',     '释放奥义'),
    ('DodgeKey',       '闪避键',     '角色闪避'),
    ('InteractKey',    '交互键',     '与物体交互'),
]

_CN_LABELS = {k: cn for k, cn, _ in _KEY_DEFS}
_EN_LABELS = {k: k for k, _, _ in _KEY_DEFS}
_NOTES = {k: note for k, _, note in _KEY_DEFS}

PRESETS = {
    '默认': {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'shift', 'InteractKey': 'f'},
    'PVE':  {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'shift', 'InteractKey': 'f'},
    'PVP':  {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'ctrl', 'InteractKey': 'f'},
    '挂机': {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'shift', 'InteractKey': 'f'},
}


class KeyBindTable(QWidget):
    """Table widget for viewing and editing key bindings."""

    key_changed = Signal(str, str)  # (arg_name, new_key)

    def __init__(self, key_config: dict = None, parent=None):
        super().__init__(parent)
        self._keys: dict[str, str] = dict(key_config) if key_config else {}
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # Preset bar
        preset_layout = QHBoxLayout()
        preset_label = QLabel('预设方案:')
        preset_label.setStyleSheet('font-size: 12px;')
        preset_layout.addWidget(preset_label)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(PRESETS.keys()))
        self._preset_combo.currentTextChanged.connect(self._apply_preset)
        preset_layout.addWidget(self._preset_combo)

        preset_layout.addStretch()

        btn_restore = QPushButton('一键还原默认')
        btn_restore.clicked.connect(self._restore_defaults)
        preset_layout.addWidget(btn_restore)

        layout.addLayout(preset_layout)

        # Table
        self._table = QTableWidget(len(_KEY_DEFS), 4)
        self._table.setHorizontalHeaderLabels([
            '功能', '当前按键', '修改', '备注'
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(2, 80)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(200)
        self._table.setMaximumHeight(260)
        layout.addWidget(self._table)

    def _load_data(self):
        for row, (key_name, cn_label, note) in enumerate(_KEY_DEFS):
            # Function name (Chinese)
            name_item = QTableWidgetItem(cn_label)
            name_item.setData(Qt.UserRole, key_name)
            self._table.setItem(row, 0, name_item)

            # Current value
            val = self._keys.get(key_name, '')
            val_item = QTableWidgetItem(val)
            val_item.setTextAlignment(Qt.AlignCenter)
            font = val_item.font()
            font.setBold(True)
            font.setPointSize(12)
            val_item.setFont(font)
            self._table.setItem(row, 1, val_item)

            # Modify button
            btn = QPushButton('\U0001F4DD')
            btn.setFixedSize(50, 30)
            btn.clicked.connect(lambda checked, r=row: self._on_capture_key(r))
            self._table.setCellWidget(row, 2, btn)

            # Note
            self._table.setItem(row, 3, QTableWidgetItem(note))

    def _on_capture_key(self, row: int):
        name_item = self._table.item(row, 0)
        key_name = name_item.data(Qt.UserRole)
        current = self._keys.get(key_name, '')

        dlg = KeyCaptureDialog(current, self)
        if dlg.exec() == KeyCaptureDialog.Accepted:
            new_key = dlg.captured_key()
            if new_key != current:
                self._keys[key_name] = new_key
                self._table.item(row, 1).setText(new_key)
                self.key_changed.emit(key_name, new_key)

    def _apply_preset(self, preset_name: str):
        preset = PRESETS.get(preset_name, {})
        if not preset:
            return
        for row, (key_name, _, _) in enumerate(_KEY_DEFS):
            if key_name in preset:
                new_val = preset[key_name]
                self._keys[key_name] = new_val
                self._table.item(row, 1).setText(new_val)
                self.key_changed.emit(key_name, new_val)

    def _restore_defaults(self):
        self._apply_preset('默认')

    def get_keys(self) -> dict[str, str]:
        return dict(self._keys)

    def set_keys(self, keys: dict[str, str]):
        self._keys = dict(keys)
        for row, (key_name, _, _) in enumerate(_KEY_DEFS):
            val = self._keys.get(key_name, '')
            self._table.item(row, 1).setText(val)
