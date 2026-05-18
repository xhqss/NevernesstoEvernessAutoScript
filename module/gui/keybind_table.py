"""
Key binding table widget using qfluentwidgets TableWidget.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem
from qfluentwidgets import TableWidget, PushButton, ComboBox, FluentIcon

from module.gui.widgets import KeyCaptureDialog
from module.i18n import tr

_KEY_DEFS = [
    ('SkillKey',       '技能键',   '普通攻击'),
    ('UltimateKey',    '终极技键', '终极技'),
    ('ArcKey',         '奥义键',   '奥义'),
    ('DodgeKey',       '闪避键',   '闪避'),
    ('InteractKey',    '交互键',   '交互'),
]

PRESETS = {
    '默认': {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'shift', 'InteractKey': 'f'},
    'PVE':  {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'shift', 'InteractKey': 'f'},
    'PVP':  {'SkillKey': 'e', 'UltimateKey': 'q', 'ArcKey': 'r', 'DodgeKey': 'ctrl', 'InteractKey': 'f'},
}


class KeyBindTable(QWidget):
    key_changed = Signal(str, str)

    def __init__(self, key_config: dict = None, parent=None):
        super().__init__(parent)
        self._keys = dict(key_config) if key_config else {}
        self._init_ui()
        self._load()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        bar = QHBoxLayout()
        bar.addStretch()
        self._preset = ComboBox()
        self._preset.addItems(list(PRESETS.keys()))
        self._preset.setCurrentText('默认')
        self._preset.setFixedWidth(120)
        self._preset.currentTextChanged.connect(self._apply_preset)
        bar.addWidget(self._preset)
        btn = PushButton(FluentIcon.CANCEL, tr('Restore Defaults'))
        btn.clicked.connect(self._restore)
        bar.addWidget(btn)
        layout.addLayout(bar)

        self._table = TableWidget(self)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([tr('Function'), tr('Current Key'), ''])
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setWordWrap(False)
        self._table.verticalHeader().hide()
        layout.addWidget(self._table)

    def _set_text(self, row, col, text):
        self._table.setItem(row, col, QTableWidgetItem(text))

    def _load(self):
        self._table.setRowCount(len(_KEY_DEFS))
        for row, (key_name, cn, note) in enumerate(_KEY_DEFS):
            self._set_text(row, 0, cn)
            self._set_text(row, 1, self._keys.get(key_name, ''))
            btn = PushButton(FluentIcon.EDIT, '')
            btn.setFixedWidth(60)
            btn.clicked.connect(lambda checked, r=row: self._capture(r))
            self._table.setCellWidget(row, 2, btn)
        self._table.resizeColumnsToContents()

    def _capture(self, row):
        key_name = _KEY_DEFS[row][0]
        current = self._keys.get(key_name, '')
        dlg = KeyCaptureDialog(current, self)
        if dlg.exec() == KeyCaptureDialog.Accepted:
            new_key = dlg.captured_key()
            if new_key != current:
                self._keys[key_name] = new_key
                self._set_text(row, 1, new_key)
                self.key_changed.emit(key_name, new_key)

    def _apply_preset(self, name):
        preset = PRESETS.get(name, {})
        for row, (key_name, _, _) in enumerate(_KEY_DEFS):
            if key_name in preset:
                self._keys[key_name] = preset[key_name]
                self._set_text(row, 1, preset[key_name])
                self.key_changed.emit(key_name, preset[key_name])

    def _restore(self):
        self._apply_preset('默认')

    def get_keys(self):
        return dict(self._keys)

    def set_keys(self, keys):
        self._keys = dict(keys)
        for row, (key_name, _, _) in enumerate(_KEY_DEFS):
            self._set_text(row, 1, self._keys.get(key_name, ''))
