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
        if content:
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
        desc = config_desc.get(key) if config_desc else None
        super().__init__(tr(key), desc)
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

        if not self.config.has_user_config():
            self.card.expandButton.hide()

        for key in self.config.keys():
            w = config_widget(self.schema, self.config, key)
            self._widgets.append(w)
            self.viewLayout.addWidget(w)

        self._adjustViewSize()

    def update_config(self):
        for w in self._widgets:
            w.update_value()
