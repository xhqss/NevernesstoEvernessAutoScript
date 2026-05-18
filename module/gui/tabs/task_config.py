"""
Task config tab — renders ConfigCards + KeyBindTable for a selected task.
Follows ok-nte's Tab + ConfigCard pattern.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout, QVBoxLayout
from qfluentwidgets import FluentIcon, PushButton, ComboBox, CardWidget, SubtitleLabel

from module.config import deep_set
from module.gui.config_adapter import GroupConfigAdapter
from module.gui.config_widgets import ConfigCard
from module.gui.keybind_table import KeyBindTable
from module.gui.communicate import communicate
from module.i18n import tr
from module.util.logger import logger


class TaskConfigTab(QWidget):
    """Scrollable tab with task selector, start/stop controls, and config cards."""

    def __init__(self, al_config, args_data, gui_labels, parent=None):
        super().__init__(parent)
        self._al_config = al_config
        self._args_data = args_data
        self._gui_labels = gui_labels
        self._task_cards = {}
        self._current_task = None

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        # ── control bar ──
        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 8)

        bl.addWidget(QLabel(tr('Tasks') + ':'))

        self._task_combo = ComboBox()
        self._task_combo.setMinimumWidth(160)
        self._task_combo.currentTextChanged.connect(
            lambda name: self.load_task(name) if name else None
        )
        bl.addWidget(self._task_combo)
        bl.addStretch()

        self._btn_start = PushButton(FluentIcon.PLAY, tr('Start'))
        self._btn_start.clicked.connect(self._on_start)
        bl.addWidget(self._btn_start)

        self._btn_stop = PushButton(FluentIcon.CLOSE, tr('Stop'))
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        bl.addWidget(self._btn_stop)

        self._btn_pause = PushButton(FluentIcon.PAUSE, tr('Pause'))
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self._on_pause)
        bl.addWidget(self._btn_pause)

        layout.addWidget(bar)

        # ── scroll area for cards ──
        from PySide6.QtWidgets import QScrollArea
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName('view')
        self._card_widget = QWidget()
        self._card_layout = QVBoxLayout(self._card_widget)
        self._card_layout.setSpacing(8)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._card_widget)
        layout.addWidget(self._scroll, 1)

    # ── task list ───────────────────────────────────────────

    def load_tasks(self, task_names):
        current = self._task_combo.currentText()
        self._task_combo.blockSignals(True)
        self._task_combo.clear()
        for tn in task_names:
            self._task_combo.addItem(tr(tn, default=tn), tn)
        # Restore selection
        idx = self._task_combo.findText(current)
        if idx >= 0:
            self._task_combo.setCurrentIndex(idx)
        self._task_combo.blockSignals(False)

    def load_task(self, task_name):
        if task_name == self._current_task:
            return
        self._current_task = task_name
        self._clear()
        self._render(task_name)

    def selected_task_name(self):
        return self._current_task

    # ── rendering ───────────────────────────────────────────

    def _clear(self):
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._task_cards.clear()

    def _render(self, task_name):
        args_task = self._args_data.get(task_name, {})
        json_task = self._al_config.data.get(task_name, {})
        gui_labels = self._gui_labels

        if not args_task and not json_task:
            self._card_layout.addWidget(
                QLabel(f'{tr("No config for")} "{task_name}"')
            )
            return

        for group_name, args_schema in args_task.items():
            if group_name == 'Storage' or not isinstance(args_schema, dict):
                continue

            json_group = json_task.get(group_name, {})
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
                self._add_keybind_card(task_name, group_name, merged, gui_labels)
                continue

            adapter = GroupConfigAdapter(
                self._al_config.data, task_name, group_name, merged
            )
            card = ConfigCard(
                group_name, merged, adapter, gui_labels.get(group_name)
            )
            self._card_layout.addWidget(card)

        self._card_layout.addStretch()

    def _add_keybind_card(self, task_name, group_name, merged, gui_labels):
        wrapper = CardWidget()
        wl = QVBoxLayout(wrapper)
        title = (gui_labels.get(group_name, {}) or {}).get('_info', group_name)
        wl.addWidget(SubtitleLabel(tr(group_name, default=title)))

        current_keys = {a: d.get('value', '') for a, d in merged.items()}
        table = KeyBindTable(current_keys)
        table.key_changed.connect(
            lambda k, v, t=task_name, g=group_name:
                deep_set(self._al_config.data, f'{t}.{g}.{k}'.split('.'), v)
        )
        table.key_changed.connect(lambda *_: self.schedule_save())
        wl.addWidget(table)
        self._card_layout.addWidget(wrapper)

    def re_render(self):
        if self._current_task:
            self._clear()
            self._render(self._current_task)

    # ── task control ────────────────────────────────────────

    def _on_start(self):
        if not self._current_task:
            return
        self._do_save()
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_pause.setEnabled(True)
        communicate.task_started.emit(self._current_task)
        logger.info(f'Task started: {self._current_task}')

    def _on_stop(self):
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_pause.setEnabled(False)
        communicate.task_stopped.emit()

    def _on_pause(self):
        if self._btn_pause.text() == tr('Pause'):
            self._btn_pause.setText(tr('Resume'))
            communicate.task_paused.emit()
        else:
            self._btn_pause.setText(tr('Pause'))
            communicate.task_resumed.emit()

    # ── auto-save ───────────────────────────────────────────

    def schedule_save(self):
        self._save_timer.start(2000)

    def _do_save(self):
        self._al_config.save()
        communicate.config_saved.emit()
