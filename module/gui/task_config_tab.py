"""
Task config tab — renders ConfigCardV2 cards and KeyBindTable for a selected task.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QScrollArea, QListWidget,
    QListWidgetItem,
)

from module.config import deep_set
from module.gui.widgets import ConfigCardV2
from module.gui.keybind_table import KeyBindTable
from module.i18n import tr as _tr


def tr(key, default=None):
    return _tr(key, default)


class TaskConfigTab:
    """Manages the Task Config tab: task list population, card rendering."""

    def __init__(self, config_manager, task_list_widget, scroll_area,
                 config_layout_widget, config_layout):
        self._cm = config_manager  # ConfigManager instance
        self._task_list = task_list_widget
        self._scroll = scroll_area
        self._config_widget = config_layout_widget
        self._config_layout = config_layout
        self._cards = []
        self._selected_task = None

        self._task_list.currentItemChanged.connect(self._on_task_selected)

    def load_tasks(self):
        self._task_list.clear()
        json_tasks = self._cm.al_config.get_task_list()
        for task_name in json_tasks:
            display = tr(task_name, default=task_name)
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, task_name)
            self._task_list.addItem(item)
        if self._task_list.count() > 0:
            self._task_list.setCurrentRow(0)

    def refresh_task_labels(self):
        for i in range(self._task_list.count()):
            item = self._task_list.item(i)
            json_name = item.data(Qt.UserRole)
            if json_name:
                item.setText(tr(json_name, default=json_name))

    def selected_task_name(self) -> str | None:
        return self._selected_task

    def cards(self) -> list:
        return self._cards

    # ── Internal ──────────────────────────────────────────────

    def _on_task_selected(self, current, previous):
        if current is None:
            return
        task_name = current.data(Qt.UserRole)
        self._selected_task = task_name
        self._render(task_name)

    def _render(self, task_name):
        # Flush previous cards to config
        for card in self._cards:
            for key, value in card.get_changes():
                deep_set(self._cm.al_config.data, keys=key.split('.'), value=value)

        # Clear layout
        while self._config_layout.count():
            item = self._config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        args_task = self._cm.args_data.get(task_name, {})
        json_task = self._cm.al_config.data.get(task_name, {})

        if not args_task and not json_task:
            label = QLabel(f'{tr("No config for")} "{task_name}"')
            label.setStyleSheet('padding: 20px;')
            self._config_layout.addWidget(label)
            return

        gui_labels = self._cm.gui_labels

        for group_name, args_schema in args_task.items():
            if group_name == 'Storage' or not isinstance(args_schema, dict):
                continue

            json_group = json_task.get(group_name, {}) if json_task else {}
            merged = {}
            for arg_name, arg_schema in args_schema.items():
                if not isinstance(arg_schema, dict):
                    continue
                entry = dict(arg_schema)
                if arg_name in json_group:
                    entry['value'] = json_group[arg_name]
                merged[arg_name] = entry

            if not merged:
                continue

            if group_name == 'NTEKeyBinding':
                self._render_keybind_card(task_name, merged, gui_labels)
                continue

            group_labels = gui_labels.get(group_name, {})
            card = ConfigCardV2(group_name, merged, task_name, gui_labels=group_labels)
            card.changed.connect(self._cm.on_card_value_changed)
            self._cards.append(card)
            self._config_layout.addWidget(card)

        self._config_layout.addStretch()

    def _render_keybind_card(self, task_name, merged, gui_labels):
        group_name = 'NTEKeyBinding'
        display_name = gui_labels.get(group_name, {}).get('_info', group_name)
        group_box = QGroupBox(display_name)

        layout = QVBoxLayout(group_box)
        layout.setContentsMargins(14, 18, 14, 14)

        current_keys = {a: d.get('value', '') for a, d in merged.items()}
        key_table = KeyBindTable(current_keys, None)
        key_table.key_changed.connect(
            lambda k, v, t=task_name, g=group_name: self._cm.on_keybind_changed(t, g, k, v)
        )
        layout.addWidget(key_table)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 8)
        wrapper_layout.addWidget(group_box)
        self._config_layout.addWidget(wrapper)

    def re_render(self):
        if self._selected_task:
            self._render(self._selected_task)
