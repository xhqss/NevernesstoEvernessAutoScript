"""
Config manager — auto-save, config CRUD, and file operations.
Handles the lifecycle of AlConfig instances backing the MainWindow.
"""

import json
import os
import copy
import shutil

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QFileDialog

from module.config import AlConfig, deep_set
from module.config.utils import read_file, write_file, filepath_config
from module.gui.communicate import communicate
from module.i18n import tr as _tr
from module.util.logger import logger


def tr(key, default=None):
    return _tr(key, default)


class ConfigManager:
    """Manages AlConfig lifecycle, auto-save, and file operations for the GUI.

    Owns: AlConfig instance, args.json data, gui_labels dict.
    Handles: config CRUD (new/save-as/delete/export/import/switch),
             auto-save with 2s debounce, unsaved-changes tracking.
    """

    def __init__(self, config_name='template'):
        self.config_name = config_name
        self._al_config = AlConfig(config_name)
        self._args_data = self._load_args_json()
        self._gui_labels = self._load_gui_labels()
        self._auto_save_timer = QTimer()
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._do_auto_save)
        self._config_cards = []  # set by MainWindow
        self._unsaved_dot = None
        self._status_label = None
        self._on_config_changed_callback = None  # called after switch to refresh toolbar

    # ── JSON / YAML loading ───────────────────────────────────

    def _load_args_json(self):
        paths = [
            os.path.join(os.path.dirname(__file__), '..', 'config', 'argument', 'args.json'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'module', 'config', 'argument', 'args.json'),
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass
        return {}

    def _load_gui_labels(self) -> dict:
        import yaml
        paths = [
            os.path.join(os.path.dirname(__file__), '..', 'config', 'argument', 'gui.yaml'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'module', 'config', 'argument', 'gui.yaml'),
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if data:
                            return data
                except Exception:
                    pass
        return {}

    # ── Accessors ─────────────────────────────────────────────

    @property
    def al_config(self):
        return self._al_config

    @property
    def args_data(self):
        return self._args_data

    @property
    def gui_labels(self):
        return self._gui_labels

    def set_unsaved_dot(self, widget):
        self._unsaved_dot = widget

    def set_status_label(self, widget):
        self._status_label = widget

    def set_config_cards(self, cards: list):
        self._config_cards = cards

    def set_config_changed_callback(self, cb):
        self._on_config_changed_callback = cb

    # ── Auto-save ─────────────────────────────────────────────

    def on_card_value_changed(self):
        self._show_unsaved(True)
        self._auto_save_timer.start(2000)

    def on_external_config_change(self):
        self._auto_save_timer.start(2000)

    def on_keybind_changed(self, task_name, group_name, key_name, value):
        path = f'{task_name}.{group_name}.{key_name}'
        deep_set(self._al_config.data, keys=path.split('.'), value=value)
        self._show_unsaved(True)
        self._auto_save_timer.start(2000)

    def _do_auto_save(self):
        for card in self._config_cards:
            for key, value in card.get_changes():
                deep_set(self._al_config.data, keys=key.split('.'), value=value)
        self._al_config.save()
        self._show_unsaved(False)
        if self._status_label:
            self._status_label.setText(tr('Auto-saved'))
        communicate.config_saved.emit()
        QTimer.singleShot(3000, lambda: self._status_label.setText(tr('Ready')) if self._status_label else None)

    def flush_pending(self):
        """Force-flush pending card changes without saving to disk."""
        for card in self._config_cards:
            for key, value in card.get_changes():
                deep_set(self._al_config.data, keys=key.split('.'), value=value)

    def _show_unsaved(self, visible):
        if self._unsaved_dot:
            self._unsaved_dot.setVisible(visible)

    # ── Config switching ──────────────────────────────────────

    def switch_config(self, name):
        if not name or name == self.config_name:
            return
        self._do_auto_save()
        self.config_name = name
        self._al_config = AlConfig(name)
        self._args_data = self._load_args_json()
        if self._on_config_changed_callback:
            self._on_config_changed_callback(name)

    # ── Config CRUD ───────────────────────────────────────────

    def new_config(self, name):
        src = filepath_config(self.config_name)
        dst = os.path.join(os.path.dirname(src), f'{name}.json')
        if os.path.exists(dst):
            return False, f'配置 "{name}" 已存在'
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            write_file(dst, self._al_config.data)
        return True, name

    def save_as(self, name):
        self._do_auto_save()
        data = copy.deepcopy(self._al_config.data)
        dst = filepath_config(name)
        write_file(dst, data)
        logger.info(f'Config saved as: {name}')

    def delete_config(self, name):
        path = filepath_config(name)
        if os.path.exists(path):
            os.remove(path)

    def export_config(self, name, parent=None):
        path, _ = QFileDialog.getSaveFileName(
            parent, tr('Export Config'), f'{name}.ntecfg',
            'NTECFG Files (*.ntecfg);;JSON Files (*.json);;All Files (*)'
        )
        if path:
            write_file(path, self._al_config.data)
            logger.info(f'Config exported: {path}')

    def import_config(self, parent=None):
        path, _ = QFileDialog.getOpenFileName(
            parent, tr('Import Config'), '',
            'NTECFG Files (*.ntecfg);;JSON Files (*.json);;All Files (*)'
        )
        if path:
            data = read_file(path)
            if data:
                name = os.path.splitext(os.path.basename(path))[0]
                dst = filepath_config(name)
                write_file(dst, data)

    def open_config_dir(self):
        config_dir = os.path.abspath('./config')
        os.makedirs(config_dir, exist_ok=True)
        os.startfile(config_dir)

    def scan_configs(self) -> list[str]:
        config_dir = os.path.normpath('./config')
        if os.path.isdir(config_dir):
            return sorted(f[:-5] for f in os.listdir(config_dir) if f.endswith('.json'))
        return []
