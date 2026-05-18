"""
MainWindow for NevernesstoEvernessAutoScript — v2.0 qfluentwidgets edition.
Follows ok-nte's MSFluentWindow + NavigationInterface + ExpandSettingCard pattern.

The shell wires together: theme, toolbar, navigation tabs, TaskConfigTab,
and the communication bus. Heavy logic lives in tabs/ and config_widgets.py.
"""

import json
import os
import copy
import shutil

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QFileDialog, QDockWidget, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QScrollArea,
)
from qfluentwidgets import (
    MSFluentWindow, NavigationInterface, NavigationItemPosition,
    FluentIcon, PushButton, ComboBox, LineEdit, SwitchButton,
    CardWidget, SubtitleLabel, setTheme, Theme, qconfig,
)

from module.config import AlConfig
from module.config.utils import read_file, write_file, filepath_config
from module.gui.communicate import communicate
from module.gui.overlay import ScreenshotViewer
from module.gui.instance_panel import InstancePanel
from module.gui.tabs.task_config import TaskConfigTab
from module.i18n import set_language
from module.i18n import tr as _tr
from module.util.logger import logger


def tr(key, default=None):
    return _tr(key, default)


# ═══════════════════════════════════════════════
#  Tab — simple scrollable wrapper
# ═══════════════════════════════════════════════

class Tab(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWidget()
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(24, 16, 24, 16)
        self.vBoxLayout.setSpacing(8)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName('view')

    def add_widget(self, w):
        self.vBoxLayout.addWidget(w)

    def add_stretch(self):
        self.vBoxLayout.addStretch()


# ═══════════════════════════════════════════════
#  ExplorerToolbar
# ═══════════════════════════════════════════════

class ExplorerToolbar(QFrame):
    config_switch = Slot(str)
    config_new = Slot(str)
    config_save = Slot(str)
    config_delete = Slot(str)
    config_export = Slot(str)
    config_import = Slot()
    multi_instance = Slot()

    def __init__(self, config_name='template', parent=None):
        super().__init__(parent)
        self._config_name = config_name
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel('\U0001F4C1  ' + tr('Configs') + ' >'))

        self._combo = ComboBox()
        self._combo.setMinimumWidth(200)
        self._combo.currentTextChanged.connect(
            lambda n: self.config_switch.emit(n) if n else None
        )
        layout.addWidget(self._combo)

        btn_new = PushButton(FluentIcon.ADD, tr('New'))
        btn_new.clicked.connect(lambda: self._on_new('blank'))
        layout.addWidget(btn_new)

        btn_save = PushButton(FluentIcon.SAVE_AS, tr('Save As'))
        btn_save.clicked.connect(lambda: self._on_save_as())
        layout.addWidget(btn_save)

        layout.addStretch()

        btn_folder = PushButton(FluentIcon.FOLDER, '')
        btn_folder.setToolTip(tr('Open Config Folder'))
        btn_folder.clicked.connect(lambda: os.startfile(os.path.abspath('./config')))
        layout.addWidget(btn_folder)

        btn_inst = PushButton(FluentIcon.PEOPLE, '')
        btn_inst.setToolTip(tr('Multi-Instance Manager'))
        btn_inst.clicked.connect(lambda: self.multi_instance.emit())
        layout.addWidget(btn_inst)

        btn_import = PushButton(FluentIcon.DOWNLOAD, '')
        btn_import.setToolTip(tr('Import Config'))
        btn_import.clicked.connect(lambda: self.config_import.emit())
        layout.addWidget(btn_import)

    def _on_new(self, mode):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, tr('New Config'),
                                         tr('Config Name') + ':')
        if ok and name.strip():
            self.config_new.emit(name.strip())

    def _on_save_as(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, tr('Save As'),
                                         tr('Config Name') + ':')
        if ok and name.strip():
            self.config_save.emit(name.strip())

    def set_config_list(self, names):
        self._combo.clear()
        self._combo.addItems(names)

    def set_current(self, name):
        self._config_name = name
        self._combo.setCurrentText(name)


# ═══════════════════════════════════════════════
#  MainWindow
# ═══════════════════════════════════════════════

class MainWindow(MSFluentWindow):

    def __init__(self, config=None):
        super().__init__()
        if isinstance(config, str):
            self._full_config = {}
            self.config_name = config
        else:
            self.config = config or {}
            self.config_name = self.config.get('config_name', 'template')
            self._full_config = config

        self._al_config = AlConfig(self.config_name)
        self._args_data = self._load_args_json()
        self._gui_labels = self._load_gui_labels()
        self.executor = None

        gui_title = self._full_config.get('gui_title', 'NTE AutoScript')
        self.setWindowTitle(f'{gui_title} - {self.config_name}')
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self._setup_navigation()
        self._connect_signals()
        self._load_task_list()

    # ── data ──────────────────────────────────────────────

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
                        return yaml.safe_load(f) or {}
                except Exception:
                    pass
        return {}

    # ── navigation / tabs ──────────────────────────────────

    def _setup_navigation(self):
        self._toolbar = ExplorerToolbar(self.config_name)
        self._toolbar.setMinimumHeight(40)

        self._task_tab = TaskConfigTab(
            self._al_config, self._args_data, self._gui_labels
        )
        self._template_tab = self._make_template_tab()
        self._debug_tab = self._make_debug_tab()
        self._log_tab = self._make_log_tab()
        self._settings_tab = self._make_settings_tab()
        self._about_tab = self._make_about_tab()

        pos = NavigationItemPosition
        self.addSubInterface(self._task_tab, FluentIcon.APPLICATION, tr('Task Config'))
        self.addSubInterface(self._template_tab, FluentIcon.PHOTO, tr('Templates'))
        self.addSubInterface(self._debug_tab, FluentIcon.DEVELOPER_TOOLS, tr('Debug'))
        self.addSubInterface(self._log_tab, FluentIcon.DOCUMENT, tr('Log'))
        self.addSubInterface(self._about_tab, FluentIcon.INFO, tr('About'),
                             position=pos.BOTTOM)
        self.addSubInterface(self._settings_tab, FluentIcon.SETTING, tr('Settings'),
                             position=pos.BOTTOM)

    # ── tab factories ──────────────────────────────────────

    def _make_template_tab(self):
        t = Tab()
        self.template_tree = QTreeWidget()
        self.template_tree.setHeaderLabels([
            tr('Name'), tr('Type'), tr('Size'), tr('Path')
        ])
        t.add_widget(self.template_tree)
        bar = QHBoxLayout()
        bar.addStretch()
        b1 = PushButton(FluentIcon.SYNC, tr('Refresh Templates'))
        b1.clicked.connect(self._refresh_templates)
        bar.addWidget(b1)
        b2 = PushButton(FluentIcon.ADD, tr('Import PNG'))
        b2.clicked.connect(self._import_template)
        bar.addWidget(b2)
        tw = QWidget()
        tw.setLayout(bar)
        t.add_widget(tw)
        t.add_stretch()
        return t

    def _make_debug_tab(self):
        t = Tab()
        self.screenshot_viewer = ScreenshotViewer()
        self.screenshot_viewer.setMinimumSize(640, 360)
        t.add_widget(self.screenshot_viewer)
        bar = QHBoxLayout()
        self.debug_info_label = QLabel(tr('No screenshot'))
        bar.addWidget(self.debug_info_label)
        bar.addStretch()
        b1 = PushButton(FluentIcon.CAMERA, tr('Take Screenshot'))
        b1.clicked.connect(lambda: communicate.task_started.emit('debug_screenshot'))
        bar.addWidget(b1)
        b2 = PushButton(FluentIcon.DELETE, tr('Clear'))
        b2.clicked.connect(lambda: self.screenshot_viewer.clear())
        bar.addWidget(b2)
        tw = QWidget()
        tw.setLayout(bar)
        t.add_widget(tw)
        return t

    def _make_log_tab(self):
        t = Tab()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName('logView')
        t.add_widget(self.log_view)
        return t

    def _make_settings_tab(self):
        t = Tab()

        general = CardWidget()
        gl = QVBoxLayout(general)
        gl.addWidget(SubtitleLabel(tr('General')))

        for label, combo_items, callback in [
            (tr('Theme'),
             [tr('Dark Mode'), tr('Light Mode')],
             lambda i: setTheme(Theme.DARK if i == 0 else Theme.LIGHT)),
            (tr('Language'),
             ['中文', 'English'],
             lambda i: set_language('zh_CN' if i == 0 else 'en')),
        ]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.addWidget(QLabel(label + ':'))
            cb = ComboBox()
            cb.addItems(combo_items)
            cb.currentIndexChanged.connect(callback)
            rl.addWidget(cb)
            rl.addStretch()
            gl.addWidget(row)

        t.add_widget(general)

        paths = CardWidget()
        pl = QVBoxLayout(paths)
        pl.addWidget(SubtitleLabel(tr('Paths')))
        for key in (tr('Config directory'), tr('Assets directory')):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.addWidget(QLabel(key + ':'))
            rl.addWidget(LineEdit())
            rl.addStretch()
            pl.addWidget(row)
        t.add_widget(paths)

        t.add_stretch()
        return t

    def _make_about_tab(self):
        t = Tab()
        card = CardWidget()
        cl = QVBoxLayout(card)
        cl.setAlignment(Qt.AlignCenter)
        cl.addWidget(QLabel(
            self._full_config.get('gui_title', 'NTE AutoScript')
        ))
        cl.addWidget(QLabel(
            f'{tr("Version")} {self._full_config.get("version", "0.1.0")}'
        ))
        cl.addWidget(QLabel('MIT License | 2024-2026'))
        t.add_widget(card)
        t.add_stretch()
        return t

    # ── task list ──────────────────────────────────────────

    def _load_task_list(self):
        tasks = self._al_config.get_task_list()
        self._task_tab.load_tasks(tasks)
        if tasks:
            self._task_tab.load_task(tasks[0])

    # ── signals ────────────────────────────────────────────

    def _connect_signals(self):
        # Toolbar
        self._toolbar.config_switch.connect(self._on_switch_config)
        self._toolbar.config_new.connect(self._on_new_config)
        self._toolbar.config_save.connect(self._on_save_as)
        self._toolbar.config_delete.connect(self._on_delete_config)
        self._toolbar.config_import.connect(self._on_import_config)
        self._toolbar.multi_instance.connect(self._show_instances)

        # Communication bus
        communicate.new_log.connect(self._on_new_log)
        communicate.log.connect(self._on_log)
        communicate.new_frame.connect(self._on_new_frame)
        communicate.new_boxes.connect(self._on_new_boxes)
        communicate.clear_boxes.connect(lambda: self.screenshot_viewer.clear())

    # ── config management ──────────────────────────────────

    def _on_switch_config(self, name):
        if not name or name == self.config_name:
            return
        self._task_tab._do_save()
        self.config_name = name
        self._al_config = AlConfig(name)
        self._args_data = self._load_args_json()
        gui_title = self._full_config.get('gui_title', 'NTE AutoScript')
        self.setWindowTitle(f'{gui_title} - {name}')
        # Rebuild task tab with new config
        old_layout = self._task_tab.parent()
        self._task_tab.deleteLater()
        self._task_tab = TaskConfigTab(self._al_config, self._args_data, self._gui_labels)
        self._load_task_list()

    def _on_new_config(self, name):
        src = filepath_config(self.config_name)
        dst = filepath_config(name)
        if os.path.exists(dst):
            from qfluentwidgets import InfoBar
            InfoBar.warning(tr('Error'), f'{tr("Config Name")} "{name}" ' + tr('exists'),
                            parent=self)
            return
        if os.path.exists(src):
            shutil.copy2(src, dst)
        self._refresh_list()

    def _on_save_as(self, name):
        self._task_tab._do_save()
        write_file(filepath_config(name), copy.deepcopy(self._al_config.data))
        self._refresh_list()

    def _on_delete_config(self, name):
        p = filepath_config(name)
        if os.path.exists(p):
            os.remove(p)
        self._refresh_list()

    def _on_import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('Import Config'), '',
            'NTECFG Files (*.ntecfg);;JSON Files (*.json)')
        if path:
            data = read_file(path)
            if data:
                name = os.path.splitext(os.path.basename(path))[0]
                write_file(filepath_config(name), data)
                self._refresh_list()

    def _refresh_list(self):
        config_dir = os.path.normpath('./config')
        if os.path.isdir(config_dir):
            names = sorted(f[:-5] for f in os.listdir(config_dir)
                           if f.endswith('.json'))
            self._toolbar.set_config_list(names)
            self._toolbar.set_current(self.config_name)

    # ── multi-instance ─────────────────────────────────────

    def _show_instances(self):
        for child in self.findChildren(QDockWidget):
            if child.windowTitle() == tr('Multi-Instance Manager'):
                child.close()
                child.deleteLater()
        dock = QDockWidget(tr('Multi-Instance Manager'), self)
        dock.setWidget(InstancePanel())
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(False)

    # ── logging / debug ────────────────────────────────────

    @Slot(str)
    def _on_new_log(self, msg):
        self.log_view.append(msg)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot(int, str)
    def _on_log(self, level, msg):
        colors = {10: '#888888', 20: '#aabbcc', 30: '#f0c040', 40: '#ff6644', 50: '#ff2222'}
        c = colors.get(level, '#aabbcc')
        self.log_view.append(f'<span style="color:{c}">{msg}</span>')

    @Slot(object)
    def _on_new_frame(self, frame):
        if frame is not None:
            self.screenshot_viewer.set_image(frame)
            h, w = frame.shape[:2]
            self.debug_info_label.setText(f'{tr("Screenshot")}: {w}x{h}')

    @Slot(object)
    def _on_new_boxes(self, boxes):
        self.screenshot_viewer.set_boxes(boxes)

    def _refresh_templates(self):
        self.template_tree.clear()
        assets_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
        if not os.path.isdir(assets_dir):
            return
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                if file.endswith('.png') or file.endswith('.gif'):
                    path = os.path.join(root, file)
                    rel = os.path.relpath(path, assets_dir)
                    sz = os.path.getsize(path)
                    self.template_tree.addTopLevelItem(QTreeWidgetItem([
                        os.path.splitext(file)[0],
                        tr('Template') if file.startswith('TEMPLATE_') else tr('Button'),
                        f'{sz / 1024:.1f} KB', rel
                    ]))

    def _import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Import PNG'), '',
                                               'PNG Images (*.png);;All Files (*)')
        if path:
            dest_dir = os.path.join(os.path.dirname(__file__), '..', '..',
                                     'assets', 'default', 'imported')
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(path, os.path.join(dest_dir, os.path.basename(path)))
            self._refresh_templates()

    # ── lifecycle ──────────────────────────────────────────

    def set_executor(self, executor):
        self.executor = executor

    def closeEvent(self, event):
        if hasattr(self, '_task_tab'):
            self._task_tab._do_save()
        communicate.quit.emit()
        if self.executor:
            self.executor.stop()
        super().closeEvent(event)


