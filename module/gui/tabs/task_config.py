"""
Task config tab — renders all NTE tasks as collapsible bars.
Each task is an ExpandSettingCard; expand to see detailed settings.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QLabel, QWidget, QHBoxLayout, QVBoxLayout, QScrollArea,
)
from qfluentwidgets import (
    FluentIcon, PushButton, ComboBox, CardWidget, SubtitleLabel,
    ExpandSettingCard, SwitchButton, IndicatorPosition,
)

from module.config import deep_set
from module.gui.config_adapter import GroupConfigAdapter
from module.gui.config_widgets import ConfigCard, config_widget
from module.gui.keybind_table import KeyBindTable
from module.gui.communicate import communicate
from module.i18n import tr
from module.util.logger import logger


class TaskBar(ExpandSettingCard):
    """A single task rendered as a collapsible bar with inline Start/Stop."""

    def __init__(self, task_name: str, al_config, args_data, gui_labels, parent=None):
        display_name = tr(task_name, default=task_name)
        super().__init__(FluentIcon.APPLICATION, display_name, '')
        self._task_name = task_name
        self._al_config = al_config
        self._args_data = args_data
        self._gui_labels = gui_labels
        self._widgets = []
        self.__init_widgets()

    def __init_widgets(self):
        self.viewLayout.setSpacing(0)
        self.viewLayout.setAlignment(Qt.AlignTop)
        self.viewLayout.setContentsMargins(10, 4, 10, 4)

        args_task = self._args_data.get(self._task_name, {})
        json_task = self._al_config.data.get(self._task_name, {})
        gui_labels = self._gui_labels

        for group_name, args_schema in args_task.items():
            if group_name == 'Storage' or not isinstance(args_schema, dict):
                continue

            json_group = json_task.get(group_name, {})
            merged = {}
            for arg_name, arg_schema in args_schema.items():
                if not isinstance(arg_schema, dict):
                    continue
                if arg_schema.get('display') == 'hide' or arg_schema.get('display') == 'disabled':
                    continue
                entry = dict(arg_schema)
                if arg_name in json_group:
                    entry['value'] = json_group[arg_name]
                merged[arg_name] = entry

            if not merged:
                continue

            if group_name == 'NTEKeyBinding':
                self._add_keybind_row(merged, gui_labels)
                continue

            adapter = GroupConfigAdapter(
                self._al_config.data, self._task_name, group_name, merged
            )
            if group_name == 'Device':
                from module.gui.config_widgets import DeviceConfigCard
                inner_card = DeviceConfigCard(
                    group_name, merged, adapter, gui_labels.get(group_name)
                )
            else:
                inner_card = ConfigCard(
                    group_name, merged, adapter, gui_labels.get(group_name)
                )
            self.viewLayout.addWidget(inner_card)

        self.setExpand(False)
        self._adjustViewSize()

    def _add_keybind_row(self, merged, gui_labels):
        wrapper = CardWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(8, 4, 8, 4)
        group_name = 'NTEKeyBinding'
        title = (gui_labels.get(group_name, {}) or {}).get('_info', group_name)
        wl.addWidget(SubtitleLabel(tr(group_name, default=title)))

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setSpacing(6)
        rl.setContentsMargins(0, 0, 0, 0)

        for key_name in ('SkillKey', 'UltimateKey', 'ArcKey', 'DodgeKey', 'InteractKey'):
            item = QWidget()
            il = QVBoxLayout(item)
            il.setSpacing(2)
            il.setContentsMargins(4, 2, 4, 2)
            lbl = QLabel(tr(key_name, default=key_name))
            lbl.setStyleSheet('font-size:11px; color:#888;')
            lbl.setAlignment(Qt.AlignCenter)
            il.addWidget(lbl)

            val = merged.get(key_name, {}).get('value', '')
            btn = QLabel(str(val))
            btn.setStyleSheet(
                'font-size:13px; font-weight:bold; padding:4px 12px; '
                'background:#2a2a3e; border:1px solid #444; border-radius:4px;'
            )
            btn.setAlignment(Qt.AlignCenter)
            il.addWidget(btn)
            rl.addWidget(item)

        wl.addWidget(row)
        self.viewLayout.addWidget(wrapper)


class TaskConfigTab(QScrollArea):
    """Scrollable tab showing all NTE tasks as collapsible bars."""

    def __init__(self, al_config=None, args_data=None, gui_labels=None, parent=None):
        super().__init__(parent)
        self.setObjectName('taskConfigTab')
        self.setWidgetResizable(True)

        self._al_config = al_config
        self._args_data = args_data or {}
        self._gui_labels = gui_labels or {}
        self._task_bars = {}

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

        self._init_ui()

    def _init_ui(self):
        self.view = QWidget()
        self.view.setObjectName('view')
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(24, 16, 24, 16)
        self.vBoxLayout.setSpacing(8)
        self.setWidget(self.view)

    def set_config(self, al_config, args_data, gui_labels):
        self._al_config = al_config
        self._args_data = args_data
        self._gui_labels = gui_labels

    def load_all_tasks(self):
        self._clear()
        if not self._al_config:
            return
        tasks = self._al_config.get_task_list()
        for task_name in tasks:
            args_task = self._args_data.get(task_name, {})
            if not args_task:
                continue
            bar = TaskBar(
                task_name, self._al_config,
                self._args_data, self._gui_labels
            )
            self._task_bars[task_name] = bar
            self.vBoxLayout.addWidget(bar)

        self.vBoxLayout.addStretch()

    def _clear(self):
        while self.vBoxLayout.count() > 0:
            item = self.vBoxLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._task_bars.clear()

    def schedule_save(self):
        self._save_timer.start(2000)

    def _do_save(self):
        if self._al_config:
            self._al_config.save()
            communicate.config_saved.emit()
