"""
Config widgets following ok-nte patterns.
- LabelAndWidget: horizontal label + widget pair
- ConfigLabelAndWidget: LabelAndWidget with config write-back
- LabelAndSwitchButton / LabelAndLineEdit / LabelAndSpinBox / LabelAndDoubleSpinBox / LabelAndDropDown
- ConfigItemFactory: type-inference → LabelAnd*
- ConfigCard: ExpandSettingCard that renders a config group
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy, QLabel
from qfluentwidgets import (
    ExpandSettingCard, FluentIcon, SwitchButton, IndicatorPosition,
    LineEdit, SpinBox, DoubleSpinBox, ComboBox,
)

from module.gui.config_adapter import GroupConfigAdapter
from module.i18n import tr as _tr


def tr(key, default=None):
    return _tr(key, default)


# ═══════════════════════════════════════════════
#  LabelAndWidget
# ═══════════════════════════════════════════════

class LabelAndWidget(QWidget):
    """Horizontal row: title label (with optional description) + trailing widget."""

    def __init__(self, title: str, content: str = None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        title_inner = QVBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName('titleLabel')
        self.title_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        title_inner.addWidget(self.title_label)

        self.content_label = None
        if content and isinstance(content, str):
            self.content_label = QLabel(content)
            self.content_label.setObjectName('contentLabel')
            self.content_label.setWordWrap(True)
            title_inner.addWidget(self.content_label)

        layout.addLayout(title_inner, stretch=0)
        layout.addStretch(1)

    def add_widget(self, widget: QWidget):
        self.layout().addWidget(widget, stretch=0)


# ═══════════════════════════════════════════════
#  ConfigLabelAndWidget
# ═══════════════════════════════════════════════

class ConfigLabelAndWidget(LabelAndWidget):
    """LabelAndWidget that reads/writes a config key."""

    def __init__(self, config_desc: dict, config: GroupConfigAdapter, key: str):
        # config_desc is the argument schema dict; we don't use it for descriptions here
        super().__init__(tr(key), None)
        self.key = key
        self.config = config

    def update_value(self):
        """Read current value from config and update widget. Override in subclasses."""
        pass

    def update_config(self, value):
        """Write value back to config."""
        self.config[self.key] = value


# ═══════════════════════════════════════════════
#  LabelAndSwitchButton
# ═══════════════════════════════════════════════

class LabelAndSwitchButton(ConfigLabelAndWidget):
    def __init__(self, config_desc, config, key):
        super().__init__(config_desc, config, key)
        self.switch = SwitchButton(indicatorPos=IndicatorPosition.RIGHT)
        self.switch.setOnText(tr('Yes'))
        self.switch.setOffText(tr('No'))
        self.update_value()
        self.switch.checkedChanged.connect(self._on_changed)
        self.add_widget(self.switch)

    def update_value(self):
        val = self.config.get(self.key)
        if self.switch.isChecked() != bool(val):
            self.switch.setChecked(bool(val))

    def _on_changed(self, checked):
        self.update_config(checked)


# ═══════════════════════════════════════════════
#  LabelAndLineEdit
# ═══════════════════════════════════════════════

class LabelAndLineEdit(ConfigLabelAndWidget):
    def __init__(self, config_desc, config, key):
        super().__init__(config_desc, config, key)
        self.edit = LineEdit()
        self.edit.setFixedWidth(220)
        self.update_value()
        self.edit.textChanged.connect(self.update_config)
        self.add_widget(self.edit)

    def update_value(self):
        val = self.config.get(self.key)
        if val is not None:
            self.edit.setText(str(val))


# ═══════════════════════════════════════════════
#  LabelAndSpinBox
# ═══════════════════════════════════════════════

class LabelAndSpinBox(ConfigLabelAndWidget):
    def __init__(self, config_desc, config, key):
        super().__init__(config_desc, config, key)
        self.spin = SpinBox()
        self.spin.setRange(0, 999999)
        self.spin.setFixedWidth(180)
        self.update_value()
        self.spin.valueChanged.connect(self.update_config)
        self.add_widget(self.spin)

    def update_value(self):
        val = self.config.get(self.key)
        if val is not None:
            try:
                self.spin.setValue(int(val))
            except (ValueError, TypeError):
                pass


# ═══════════════════════════════════════════════
#  LabelAndDoubleSpinBox
# ═══════════════════════════════════════════════

class LabelAndDoubleSpinBox(ConfigLabelAndWidget):
    def __init__(self, config_desc, config, key):
        super().__init__(config_desc, config, key)
        self.spin = DoubleSpinBox()
        self.spin.setRange(0, 999999)
        self.spin.setDecimals(4)
        self.spin.setFixedWidth(180)
        self.update_value()
        self.spin.valueChanged.connect(self.update_config)
        self.add_widget(self.spin)

    def update_value(self):
        val = self.config.get(self.key)
        if val is not None:
            try:
                self.spin.setValue(float(val))
            except (ValueError, TypeError):
                pass


# ═══════════════════════════════════════════════
#  LabelAndDropDown
# ═══════════════════════════════════════════════

class LabelAndDropDown(ConfigLabelAndWidget):
    def __init__(self, config_desc, config, key, options: list):
        super().__init__(config_desc, config, key)
        self._options = [str(o) for o in options]
        self.combo = ComboBox()
        self.combo.addItems(self._options)
        self.combo.setFixedWidth(200)
        self.update_value()
        self.combo.currentTextChanged.connect(self.update_config)
        self.add_widget(self.combo)

    def update_value(self):
        val = str(self.config.get(self.key))
        if val in self._options:
            self.combo.setCurrentText(val)


# ═══════════════════════════════════════════════
#  ConfigItemFactory
# ═══════════════════════════════════════════════

def config_widget(schema: dict, config: GroupConfigAdapter, key: str, task=None):
    """Factory: inspect the argument schema and return the right LabelAnd* widget."""
    arg_schema = schema.get(key, {})
    if not isinstance(arg_schema, dict):
        arg_schema = {}

    arg_type = arg_schema.get('type', '')
    options = arg_schema.get('option', None)
    value = config.get(key)

    # Explicit type from schema
    if options:
        return LabelAndDropDown(schema, config, key, options)
    if arg_type == 'checkbox' or isinstance(value, bool):
        return LabelAndSwitchButton(schema, config, key)
    if isinstance(value, float):
        return LabelAndDoubleSpinBox(schema, config, key)
    if isinstance(value, int):
        return LabelAndSpinBox(schema, config, key)
    # Default: string
    return LabelAndLineEdit(schema, config, key)


# ═══════════════════════════════════════════════
#  ConfigCard
# ═══════════════════════════════════════════════

class ConfigCard(ExpandSettingCard):
    """Collapsible card that renders a config group using ConfigItemFactory.

    Follows ok-nte's ConfigCard(ExpandSettingCard) pattern exactly.
    """

    def __init__(self, group_name: str, schema: dict, config: GroupConfigAdapter,
                 gui_labels: dict = None, icon=FluentIcon.INFO):
        display_name = (gui_labels or {}).get('_info', group_name) if gui_labels else group_name
        super().__init__(icon, tr(group_name, default=display_name), '')
        self.config = config
        self.schema = schema
        self.gui_labels = gui_labels or {}
        self._widgets = []
        self.__init_widgets()

    def __init_widgets(self):
        self.viewLayout.setSpacing(0)
        self.viewLayout.setAlignment(Qt.AlignTop)
        self.viewLayout.setContentsMargins(10, 0, 10, 0)

        for key in self.config.keys():
            w = config_widget(self.schema, self.config, key)
            self._widgets.append(w)
            self.viewLayout.addWidget(w)

        self.setExpand(True)
        self._adjustViewSize()

    def update_config(self):
        for w in self._widgets:
            w.update_value()


# ═══════════════════════════════════════════════
#  DeviceConfigCard — platform-aware device config
# ═══════════════════════════════════════════════

# PC-only screenshot methods
PC_SCREENSHOT_METHODS = ["WindowsGraphics", "BitBlt"]
# Emulator-only screenshot methods
EMULATOR_SCREENSHOT_METHODS = ["ADB", "scrcpy", "nemu_ipc"]
# PC-only control methods
PC_CONTROL_METHODS = ["PostMessage", "PyDirectInput"]
# Emulator-only control methods
EMULATOR_CONTROL_METHODS = ["ADB", "minitouch", "maatouch", "nemu_ipc"]

# Serial help text (from ALAS)
SERIAL_HELP_TEXT = (
    '常见的模拟器 Serial：\n'
    '  - MuMu模拟器/MuMu模拟器X: 127.0.0.1:7555\n'
    '  - MuMu模拟器12: 127.0.0.1:16384\n'
    '  - 蓝叠模拟器: 127.0.0.1:5555\n'
    '  - 蓝叠4 Hyper-v版: bluestacks4-hyperv\n'
    '  - 蓝叠5 Hyper-v版: bluestacks5-hyperv\n'
    '  - 夜神模拟器: 127.0.0.1:62001\n'
    '  - 夜神模拟器64位: 127.0.0.1:59865\n'
    '  - 逍遥模拟器: 127.0.0.1:21503\n'
    '  - 雷电模拟器: emulator-5554 或 127.0.0.1:5555'
)


class DeviceConfigCard(ExpandSettingCard):
    """Device config with platform-dependent option filtering and Serial help."""

    def __init__(self, group_name: str, schema: dict, config: GroupConfigAdapter,
                 gui_labels: dict = None, icon=FluentIcon.INFO):
        display_name = (gui_labels or {}).get('_info', group_name) if gui_labels else group_name
        super().__init__(icon, tr(group_name, default=display_name), '')
        self.config = config
        self.schema = schema
        self.gui_labels = gui_labels or {}
        self._widgets = []
        self._platform_combo = None
        self._serial_row = None
        self._serial_help = None
        self._screenshot_combo = None
        self._control_combo = None
        self.__init_widgets()

    def __init_widgets(self):
        self.viewLayout.setSpacing(0)
        self.viewLayout.setAlignment(Qt.AlignTop)
        self.viewLayout.setContentsMargins(10, 0, 10, 0)

        for key in self.config.keys():
            display = self.schema.get(key, {}).get('display', '')
            if display == 'hide':
                continue

            if key == 'Platform':
                w = self._make_platform_widget(key)
                self._platform_combo = w.combo
                w.combo.currentTextChanged.connect(self._on_platform_changed)
            elif key == 'EmulatorSerial':
                w = self._make_serial_widget(key)
                self._serial_row = w
                # Add help text below serial
                self._serial_help = QLabel(SERIAL_HELP_TEXT)
                self._serial_help.setObjectName('serialHelp')
                self._serial_help.setWordWrap(True)
                self._serial_help.setStyleSheet(
                    'font-size:10px; color:#888; padding:2px 8px; margin-left:12px;'
                )
                self._serial_help.setVisible(False)
            elif key == 'ScreenshotMethod':
                w = self._make_dropdown_widget(key, self.schema.get(key, {}).get('option', []))
                self._screenshot_combo = w.combo
            elif key == 'ControlMethod':
                w = self._make_dropdown_widget(key, self.schema.get(key, {}).get('option', []))
                self._control_combo = w.combo
            else:
                w = config_widget(self.schema, self.config, key)

            self._widgets.append(w)
            self.viewLayout.addWidget(w)
            if key == 'EmulatorSerial' and self._serial_help:
                self.viewLayout.addWidget(self._serial_help)

        # Initial platform state
        platform = self.config.get('Platform', 'PC')
        self._on_platform_changed(str(platform))

        self.setExpand(True)
        self._adjustViewSize()

    def _make_platform_widget(self, key):
        options = self.schema.get(key, {}).get('option', ['PC', 'Emulator'])
        w = LabelAndDropDown(self.schema, self.config, key, options)
        return w

    def _make_serial_widget(self, key):
        w = LabelAndLineEdit(self.schema, self.config, key)
        w.title_label.setText(tr('EmulatorSerial', default='Emulator Serial'))
        return w

    def _make_dropdown_widget(self, key, options):
        w = LabelAndDropDown(self.schema, self.config, key, options)
        return w

    def _on_platform_changed(self, platform):
        is_emulator = (platform == 'Emulator')

        if self._serial_row:
            self._serial_row.setVisible(is_emulator)
        if self._serial_help:
            self._serial_help.setVisible(is_emulator)

        if is_emulator:
            ss_opts = EMULATOR_SCREENSHOT_METHODS
            ctrl_opts = EMULATOR_CONTROL_METHODS
        else:
            ss_opts = PC_SCREENSHOT_METHODS
            ctrl_opts = PC_CONTROL_METHODS

        if self._screenshot_combo:
            current = self._screenshot_combo.currentText()
            self._screenshot_combo.blockSignals(True)
            self._screenshot_combo.clear()
            self._screenshot_combo.addItems(ss_opts)
            if current in ss_opts:
                self._screenshot_combo.setCurrentText(current)
            else:
                self._screenshot_combo.setCurrentIndex(0)
                self.config['ScreenshotMethod'] = ss_opts[0]
            self._screenshot_combo.blockSignals(False)

        if self._control_combo:
            current = self._control_combo.currentText()
            self._control_combo.blockSignals(True)
            self._control_combo.clear()
            self._control_combo.addItems(ctrl_opts)
            if current in ctrl_opts:
                self._control_combo.setCurrentText(current)
            else:
                self._control_combo.setCurrentIndex(0)
                self.config['ControlMethod'] = ctrl_opts[0]
            self._control_combo.blockSignals(False)

        self._adjustViewSize()

    def update_config(self):
        for w in self._widgets:
            if hasattr(w, 'update_value'):
                w.update_value()
