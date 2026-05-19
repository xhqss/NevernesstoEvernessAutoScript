"""
MainWindow for NevernesstoEvernessAutoScript — v2.3 edition.
Browser-style multi-instance tabs + Overview/Device/Tasks/GameTools/Debug/Settings nav.
Theme-aware, i18n-switchable, with ALAS-style git commit display.
"""

import json
import os
import copy
import shutil
import subprocess

from PySide6.QtCore import Qt, QTimer, Slot, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QFileDialog, QTextEdit, QTabBar, QPushButton, QMenu,
    QScrollArea, QSplitter, QStackedWidget,
)
from qfluentwidgets import (
    MSFluentWindow, NavigationInterface, NavigationItemPosition,
    FluentIcon, PushButton, ComboBox, LineEdit, SwitchButton,
    CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel,
    TextEdit, setTheme, Theme, qconfig, setThemeColor,
    ExpandSettingCard, NavigationBarPushButton,
)

from module.config import AlConfig
from module.config.utils import read_file, write_file, filepath_config
from module.gui.communicate import communicate
from module.gui.overlay import ScreenshotViewer
from module.i18n import set_language, tr as _tr
from module.util.logger import logger


def tr(key, default=None):
    return _tr(key, default)


# ═══════════════════════════════════════════════
#  Tab — scrollable wrapper
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

    def add_widget(self, w, stretch=0):
        self.vBoxLayout.addWidget(w, stretch)

    def add_stretch(self):
        self.vBoxLayout.addStretch()


# ═══════════════════════════════════════════════
#  ConfigTabBar — browser-style multi-instance tabs
# ═══════════════════════════════════════════════

class ConfigTabBar(QFrame):
    config_switch = Signal(str)
    config_new = Signal(str)
    config_copy = Signal(str)
    config_delete = Signal(str)
    config_export = Signal(str)
    config_import = Signal()

    def __init__(self, config_name='neas1', parent=None):
        super().__init__(parent)
        self._config_name = config_name
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 8, 2)
        layout.setSpacing(2)

        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.setShape(QTabBar.RoundedNorth)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setMinimumWidth(100)
        self._tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._on_context_menu)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close)
        layout.addWidget(self._tab_bar, stretch=1)

        btn_add = QPushButton('+')
        btn_add.setFixedSize(28, 28)
        btn_add.setToolTip(tr('New Config'))
        btn_add.clicked.connect(lambda: self._on_new())
        layout.addWidget(btn_add)

        btn_folder = PushButton(FluentIcon.FOLDER, '')
        btn_folder.setFixedSize(32, 28)
        btn_folder.setToolTip(tr('Open Config Folder'))
        btn_folder.clicked.connect(lambda: os.startfile(os.path.abspath('./config')))
        layout.addWidget(btn_folder)

        btn_import = PushButton(FluentIcon.DOWNLOAD, '')
        btn_import.setFixedSize(32, 28)
        btn_import.setToolTip(tr('Import Config'))
        btn_import.clicked.connect(lambda: self.config_import.emit())
        layout.addWidget(btn_import)

    def _on_tab_changed(self, index):
        if index >= 0:
            name = self._tab_bar.tabData(index)
            if name and name != self._config_name:
                self.config_switch.emit(name)

    def _on_tab_close(self, index):
        name = self._tab_bar.tabData(index)
        if name and self._tab_bar.count() > 1:
            self.config_delete.emit(name)

    def _on_context_menu(self, pos):
        index = self._tab_bar.tabAt(pos)
        if index < 0:
            return
        name = self._tab_bar.tabData(index)
        menu = QMenu(self)
        act_copy = menu.addAction(tr('Duplicate Config'))
        act_export = menu.addAction(tr('Export Config'))
        act_delete = menu.addAction(tr('Delete Current Config'))
        action = menu.exec(self._tab_bar.mapToGlobal(pos))
        if action == act_copy:
            self.config_copy.emit(name)
        elif action == act_export:
            self.config_export.emit(name)
        elif action == act_delete and self._tab_bar.count() > 1:
            self.config_delete.emit(name)

    def _on_new(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, tr('New Config'),
                                         tr('Config Name') + ':')
        if ok and name.strip():
            self.config_new.emit(name.strip())

    def set_config_list(self, names):
        current = self._config_name
        self._tab_bar.blockSignals(True)
        while self._tab_bar.count() > 0:
            self._tab_bar.removeTab(0)
        for n in names:
            self._tab_bar.addTab(n)
            self._tab_bar.setTabData(self._tab_bar.count() - 1, n)
        self._tab_bar.blockSignals(False)
        self.set_current(current)

    def set_current(self, name):
        self._config_name = name
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == name:
                self._tab_bar.blockSignals(True)
                self._tab_bar.setCurrentIndex(i)
                self._tab_bar.blockSignals(False)
                return

    def add_tab(self, name):
        idx = self._tab_bar.addTab(name)
        self._tab_bar.setTabData(idx, name)
        self._tab_bar.setCurrentIndex(idx)

    def remove_tab(self, name):
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == name:
                self._tab_bar.removeTab(i)
                return


# ═══════════════════════════════════════════════
#  MainWindow
# ═══════════════════════════════════════════════

class MainWindow(MSFluentWindow):

    TASKS_CATEGORY = ['Daily', 'Fishing', 'Anomaly', 'Rhythm', 'Heist']
    GAME_TOOLS_CATEGORY = ['AutoCombat', 'SkipDialog', 'FastTravel']

    def __init__(self, config=None):
        super().__init__()
        if isinstance(config, str):
            self._full_config = {}
            self.config_name = config
        else:
            self.config = config or {}
            self.config_name = self.config.get('config_name', 'neas1')
            self._full_config = config

        self._al_config = AlConfig(self.config_name)
        self._args_data = self._load_args_json()
        self._gui_labels = self._load_gui_labels()
        self.executor = None
        self._running_task = None
        self._all_tabs = {}
        self._nav_buttons = []

        self.setWindowTitle('Neverness to Everness AutoScript')
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self._insert_tab_bar()
        self._setup_navigation()
        self._connect_signals()
        self._connect_theme()
        self._refresh_list()
        self._load_all_tabs()

    # ── data loading ──────────────────────────────────────

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

    # ── tab bar insertion into MSFluentWindow layout ──────

    def _insert_tab_bar(self):
        """Insert ConfigTabBar between title bar and stacked content area."""
        self._tab_bar = ConfigTabBar(self.config_name)
        self._tab_bar.setMinimumHeight(36)
        self._tab_bar.setStyleSheet(
            'QFrame { background:#1e1e2e; border-bottom:1px solid #333; }'
            'QTabBar::tab { background:#252536; color:#ccc; padding:6px 16px; '
            'border:1px solid #333; border-bottom:none; border-top-left-radius:4px; '
            'border-top-right-radius:4px; margin-right:2px; }'
            'QTabBar::tab:selected { background:#2d2d44; color:#fff; }'
            'QTabBar::tab:hover { background:#2a2a40; }'
            'QTabBar::close-button { image:none; }'
        )

        # Take stackedWidget out of hBoxLayout, wrap it with tab bar
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self._tab_bar)
        wl.addWidget(self.stackedWidget, stretch=1)

        # Remove stackedWidget from hBoxLayout and insert wrapper
        self.hBoxLayout.removeWidget(self.stackedWidget)
        self.hBoxLayout.addWidget(wrapper, stretch=1)

    # ── navigation ───────────────────────────────────────

    def _setup_navigation(self):
        self._overview_tab = self._make_overview_tab()
        self._device_tab = self._make_device_settings_tab()
        self._tasks_tab = self._make_tasks_tab()
        self._gametools_tab = self._make_gametools_tab()
        self._debug_tab = self._make_debug_tab()
        self._settings_tab = self._make_settings_tab()

        tab_info = [
            (self._overview_tab, FluentIcon.HOME, tr('Overview'), 'overviewTab'),
            (self._device_tab, FluentIcon.CONNECT, tr('Device Settings'), 'deviceTab'),
            (self._tasks_tab, FluentIcon.APPLICATION, tr('Tasks'), 'tasksTab'),
            (self._gametools_tab, FluentIcon.COMMAND_PROMPT, tr('Game Tools'), 'gametoolsTab'),
            (self._debug_tab, FluentIcon.DEVELOPER_TOOLS, tr('Debug'), 'debugTab'),
        ]

        self._nav_buttons = []
        for tab, icon, text, name in tab_info:
            if not tab.objectName():
                tab.setObjectName(name)
            btn = self.addSubInterface(tab, icon, text, position=NavigationItemPosition.SCROLL)
            self._nav_buttons.append((btn, text))
            self._all_tabs[name] = tab

        # Settings at bottom-left
        self._settings_tab.setObjectName('settingsTab')
        self.addSubInterface(
            self._settings_tab, FluentIcon.SETTING, tr('Settings'),
            position=NavigationItemPosition.BOTTOM
        )
        self._all_tabs['settingsTab'] = self._settings_tab

    def _rebuild_navigation_labels(self):
        """Refresh navigation button texts after language change."""
        for btn, _ in self._nav_buttons:
            objname = btn.property('routeKey', None)
            # text refresh happens via tr(); we re-create navigation from scratch
        # Simplest correct approach: recreate whole navigation
        self._nav_buttons = []
        # Remove old nav items
        for name in list(self._all_tabs.keys()):
            tab = self._all_tabs.pop(name)
            self.navigationInterface.removeWidget(tab.objectName())
        # Re-add
        self._setup_navigation()
        self._load_all_tabs()

    # ── theme ─────────────────────────────────────────────

    def _connect_theme(self):
        qconfig.themeChanged.connect(lambda t: self._on_theme_changed())

    def _on_theme_changed(self):
        pass  # qfluentwidgets handles widget styling automatically

    # ── Overview Tab ──────────────────────────────────────

    def _make_overview_tab(self):
        t = Tab()
        t.vBoxLayout.setSpacing(6)

        # Top action bar: Connect + Start + Stop
        action_bar = CardWidget()
        abl = QHBoxLayout(action_bar)
        abl.setContentsMargins(12, 8, 12, 8)

        self._ov_btn_connect = PushButton(FluentIcon.LINK, tr('Connect'))
        self._ov_btn_connect.setMinimumHeight(40)
        abl.addWidget(self._ov_btn_connect)

        self._ov_btn_start = PushButton(FluentIcon.PLAY, tr('Start'))
        self._ov_btn_start.setMinimumHeight(40)
        self._ov_btn_start.clicked.connect(self._on_overview_start)
        abl.addWidget(self._ov_btn_start)

        self._ov_btn_stop = PushButton(FluentIcon.CLOSE, tr('Stop'))
        self._ov_btn_stop.setMinimumHeight(40)
        self._ov_btn_stop.setEnabled(False)
        self._ov_btn_stop.clicked.connect(self._on_overview_stop)
        abl.addWidget(self._ov_btn_stop)
        abl.addStretch()
        t.add_widget(action_bar)

        # Main body: 3-panel horizontal split
        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setSpacing(8)
        bl.setContentsMargins(0, 0, 0, 0)

        # Left 1/5: 3 vertical task status panels
        left_panel = QWidget()
        ll = QVBoxLayout(left_panel)
        ll.setSpacing(4)
        ll.setContentsMargins(0, 0, 0, 0)
        self._status_lists = {}
        for title, key in [
            (tr('Running Tasks'), 'running'),
            (tr('Queued Tasks'), 'queued'),
            (tr('Waiting Tasks'), 'waiting'),
        ]:
            card = CardWidget()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 4, 6, 4)
            cl.setSpacing(2)
            cl.addWidget(SubtitleLabel(title))
            lst = QVBoxLayout()
            lst.setSpacing(1)
            cl.addLayout(lst)
            cl.addStretch()
            ll.addWidget(card)
            self._status_lists[key] = lst
        ll.addStretch()
        bl.addWidget(left_panel, stretch=1)

        # Center 3/5: game preview (flexible 16:9)
        center_panel = QWidget()
        cpl = QVBoxLayout(center_panel)
        cpl.setSpacing(4)
        cpl.setContentsMargins(0, 0, 0, 0)

        preview_card = CardWidget()
        pcl = QVBoxLayout(preview_card)
        pcl.setContentsMargins(8, 4, 8, 8)
        pcl.addWidget(SubtitleLabel(tr('Game Preview')))
        self._preview_label = QLabel(tr('No screenshot'))
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumHeight(200)
        self._preview_label.setSizePolicy(
            self._preview_label.sizePolicy().horizontalPolicy(),
            self._preview_label.sizePolicy().verticalPolicy().Expanding
        )
        self._preview_label.setStyleSheet(
            'background:#1a1a2e; border:1px solid #333; color:#888; border-radius:4px;'
        )
        pcl.addWidget(self._preview_label, stretch=1)
        cpl.addWidget(preview_card, stretch=3)
        # Bottom blank
        cpl.addStretch(2)
        bl.addWidget(center_panel, stretch=2)

        # Right 2/5: compact log (1/3 width target)
        right_panel = QWidget()
        rl = QVBoxLayout(right_panel)
        rl.setSpacing(4)
        rl.setContentsMargins(0, 0, 0, 0)

        log_card = CardWidget()
        lcl = QVBoxLayout(log_card)
        lcl.setContentsMargins(8, 4, 8, 8)
        lcl.addWidget(SubtitleLabel(tr('Log')))
        self._compact_log = QTextEdit()
        self._compact_log.setReadOnly(True)
        self._compact_log.setObjectName('compactLog')
        self._compact_log.setMinimumWidth(260)
        lcl.addWidget(self._compact_log)
        rl.addWidget(log_card)
        bl.addWidget(right_panel, stretch=2)

        t.add_widget(body, stretch=1)
        return t

    # ── Device Settings Tab ────────────────────────────────

    def _make_device_settings_tab(self):
        t = Tab()
        t.setObjectName('deviceTab')
        self._device_scroll = t
        return t

    def _refresh_device_settings(self):
        t = self._device_scroll
        while t.vBoxLayout.count() > 0:
            item = t.vBoxLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from module.gui.config_adapter import GroupConfigAdapter
        from module.gui.config_widgets import DeviceConfigCard, ConfigCard

        default_task = self._args_data.get('DefaultTask', {})
        json_task = self._al_config.data.get('DefaultTask', {})
        gui_labels = self._gui_labels

        # Device
        dev_schema = default_task.get('Device', {})
        if dev_schema:
            json_dev = json_task.get('Device', {})
            merged = self._merge_schema(dev_schema, json_dev)
            adapter = GroupConfigAdapter(self._al_config.data, 'DefaultTask', 'Device', merged)
            t.add_widget(DeviceConfigCard('Device', merged, adapter, gui_labels.get('Device')))

        # Window
        win_schema = default_task.get('Window', {})
        if win_schema:
            json_win = json_task.get('Window', {})
            merged = self._merge_schema(win_schema, json_win)
            adapter = GroupConfigAdapter(self._al_config.data, 'DefaultTask', 'Window', merged)
            t.add_widget(ConfigCard('Window', merged, adapter, gui_labels.get('Window')))

        # Launcher (deduplicated)
        launch_schema = default_task.get('NTELauncher', {})
        if launch_schema:
            json_launch = json_task.get('NTELauncher', {})
            merged = self._merge_schema(launch_schema, json_launch, skip_keys=['GameClass'])
            if merged:
                adapter = GroupConfigAdapter(self._al_config.data, 'DefaultTask', 'NTELauncher', merged)
                t.add_widget(ConfigCard('NTELauncher', merged, adapter, gui_labels.get('NTELauncher')))

        # Restart
        rst_schema = default_task.get('Restart', {})
        if rst_schema:
            json_rst = json_task.get('Restart', {})
            merged = self._merge_schema(rst_schema, json_rst)
            if merged:
                adapter = GroupConfigAdapter(self._al_config.data, 'DefaultTask', 'Restart', merged)
                t.add_widget(ConfigCard('Restart', merged, adapter, gui_labels.get('Restart')))

        # Key Bindings (horizontal row)
        self._add_keybind_to_tab(t)
        t.add_stretch()

    def _merge_schema(self, schema, json_data, skip_keys=None):
        skip_keys = skip_keys or []
        merged = {}
        for arg_name, arg_schema in schema.items():
            if not isinstance(arg_schema, dict):
                continue
            if arg_name in skip_keys:
                continue
            if arg_schema.get('display') == 'disabled':
                continue
            entry = dict(arg_schema)
            if arg_name in json_data:
                entry['value'] = json_data[arg_name]
            merged[arg_name] = entry
        return merged

    def _add_keybind_to_tab(self, t):
        default_task = self._args_data.get('DefaultTask', {})
        kb_schema = default_task.get('NTEKeyBinding', {})
        if not kb_schema:
            return
        json_task = self._al_config.data.get('DefaultTask', {})
        json_kb = json_task.get('NTEKeyBinding', {})

        card = CardWidget()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 6, 10, 6)
        info = (self._gui_labels.get('NTEKeyBinding', {}) or {}).get('_info', 'NTEKeyBinding')
        cl.addWidget(SubtitleLabel(tr('NTEKeyBinding', default=info)))

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setSpacing(6)
        rl.setContentsMargins(0, 0, 0, 0)

        for key_name in ('SkillKey', 'UltimateKey', 'ArcKey', 'DodgeKey', 'InteractKey'):
            item = QWidget()
            il = QVBoxLayout(item)
            il.setSpacing(2)
            il.setContentsMargins(4, 2, 4, 2)
            lbl = BodyLabel(tr(key_name, default=key_name))
            lbl.setAlignment(Qt.AlignCenter)
            il.addWidget(lbl)
            val = kb_schema.get(key_name, {}).get('value', '')
            if key_name in json_kb:
                val = json_kb[key_name]
            btn = BodyLabel(str(val))
            btn.setAlignment(Qt.AlignCenter)
            il.addWidget(btn)
            rl.addWidget(item)

        cl.addWidget(row)
        t.add_widget(card)

    # ── Tasks Tab ──────────────────────────────────────────

    def _make_tasks_tab(self):
        t = Tab()
        t.setObjectName('tasksTab')
        self._tasks_scroll = t
        return t

    def _refresh_tasks(self):
        t = self._tasks_scroll
        while t.vBoxLayout.count() > 0:
            item = t.vBoxLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        from module.gui.tabs.task_config import TaskBar
        for task_name in self.TASKS_CATEGORY:
            if self._args_data.get(task_name):
                bar = TaskBar(task_name, self._al_config, self._args_data, self._gui_labels)
                t.add_widget(bar)
        t.add_stretch()

    # ── Game Tools Tab ─────────────────────────────────────

    def _make_gametools_tab(self):
        t = Tab()
        t.setObjectName('gametoolsTab')
        self._gametools_scroll = t
        return t

    def _refresh_gametools(self):
        t = self._gametools_scroll
        while t.vBoxLayout.count() > 0:
            item = t.vBoxLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        from module.gui.tabs.task_config import TaskBar
        for task_name in self.GAME_TOOLS_CATEGORY:
            if self._args_data.get(task_name):
                bar = TaskBar(task_name, self._al_config, self._args_data, self._gui_labels)
                t.add_widget(bar)
        t.add_stretch()

    # ── Debug Tab ──────────────────────────────────────────

    def _make_debug_tab(self):
        w = QWidget()
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._screenshot_viewer = ScreenshotViewer()
        self._screenshot_viewer.setMinimumSize(640, 360)
        ll.addWidget(self._screenshot_viewer)
        bar = QHBoxLayout()
        self._debug_info_label = BodyLabel(tr('No screenshot'))
        bar.addWidget(self._debug_info_label)
        bar.addStretch()
        b1 = PushButton(FluentIcon.CAMERA, tr('Take Screenshot'))
        b1.clicked.connect(lambda: communicate.task_started.emit('debug_screenshot'))
        bar.addWidget(b1)
        b2 = PushButton(FluentIcon.DELETE, tr('Clear'))
        b2.clicked.connect(self._screenshot_viewer.clear)
        bar.addWidget(b2)
        ll.addLayout(bar)

        right = QScrollArea()
        right.setWidgetResizable(True)
        right_content = QWidget()
        rl = QVBoxLayout(right_content)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(8)
        rl.addWidget(SubtitleLabel(tr('Debug Tasks')))

        from module.gui.config_adapter import GroupConfigAdapter
        from module.gui.config_widgets import ConfigCard

        for group_name in ('NTEMonthlyCard', 'NTESoundTrigger'):
            default_task = self._args_data.get('DefaultTask', {})
            group_schema = default_task.get(group_name, {})
            if not group_schema:
                continue
            json_task = self._al_config.data.get('DefaultTask', {})
            json_group = json_task.get(group_name, {})
            merged = self._merge_schema(group_schema, json_group)
            if merged:
                adapter = GroupConfigAdapter(self._al_config.data, 'DefaultTask', group_name, merged)
                card = ConfigCard(group_name, merged, adapter, self._gui_labels.get(group_name))
                rl.addWidget(card)

        rl.addStretch()
        right.setWidget(right_content)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer = QVBoxLayout(w)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.addWidget(splitter)
        return w

    # ── Settings Tab ───────────────────────────────────────

    def _make_settings_tab(self):
        t = Tab()
        t.vBoxLayout.setSpacing(12)

        # Theme — non-collapsible bar
        theme_card = CardWidget()
        tl = QHBoxLayout(theme_card)
        tl.setContentsMargins(16, 12, 16, 12)
        tl.addWidget(BodyLabel(tr('Theme') + ':'))
        self._theme_combo = ComboBox()
        self._theme_combo.addItems([tr('Dark Mode'), tr('Light Mode')])
        self._theme_combo.currentIndexChanged.connect(
            lambda i: setTheme(Theme.DARK if i == 0 else Theme.LIGHT, lazy=False)
        )
        tl.addWidget(self._theme_combo)
        tl.addStretch()
        t.add_widget(theme_card)

        # Language — non-collapsible bar
        lang_card = CardWidget()
        ll = QHBoxLayout(lang_card)
        ll.setContentsMargins(16, 12, 16, 12)
        ll.addWidget(BodyLabel(tr('Language') + ':'))
        self._lang_combo = ComboBox()
        self._lang_combo.addItems(['中文', 'English'])
        self._lang_combo.currentIndexChanged.connect(
            lambda i: self._on_language_change('zh_CN' if i == 0 else 'en')
        )
        ll.addWidget(self._lang_combo)
        ll.addStretch()
        t.add_widget(lang_card)

        # Git commit log — ALAS-style table
        git_card = CardWidget()
        gl = QVBoxLayout(git_card)
        gl.setContentsMargins(16, 12, 16, 12)
        gl.addWidget(SubtitleLabel(tr('Git Commit Log')))

        self._git_log = QTextEdit()
        self._git_log.setReadOnly(True)
        self._git_log.setMinimumHeight(300)
        self._git_log.setObjectName('gitLog')
        self._git_log.setStyleSheet('font-family:Consolas,monospace; font-size:12px;')
        gl.addWidget(self._git_log)
        self._load_git_log()
        t.add_widget(git_card)

        t.add_stretch()
        return t

    def _load_git_log(self):
        try:
            repo = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            result = subprocess.run(
                ['git', 'log', '--pretty=format:%h  %an  %ad  %s', '--date=iso', '-30'],
                capture_output=True, text=True, timeout=10,
                cwd=repo
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                header = f'{"SHA1":<10} {"Author":<20} {"Time":<22} Message'
                formatted = header + '\n' + '-' * 90 + '\n' + '\n'.join(lines)
                self._git_log.setText(formatted)
            else:
                self._git_log.setText(tr('No git history available'))
        except Exception as e:
            self._git_log.setText(f'{tr("No git history available")}: {e}')

    def _on_language_change(self, lang):
        set_language(lang)
        self._gui_labels = self._load_gui_labels()
        self._rebuild_navigation_labels()

    # ── tab loading ─────────────────────────────────────────

    def _load_all_tabs(self):
        self._refresh_device_settings()
        self._refresh_tasks()
        self._refresh_gametools()
        self._refresh_overview()

    def _refresh_overview(self):
        for lst in self._status_lists.values():
            while lst.count() > 0:
                item = lst.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        all_data = self._al_config.data

        if self._running_task:
            label = BodyLabel(f'  {tr(self._running_task, default=self._running_task)}')
            self._status_lists['running'].addWidget(label)

        import datetime
        now = datetime.datetime.now()
        for task_name in self.TASKS_CATEGORY + self.GAME_TOOLS_CATEGORY:
            if task_name == self._running_task:
                continue
            tdata = all_data.get(task_name, {})
            sched = tdata.get('Scheduler', {})
            if not sched.get('Enable', False):
                continue
            next_run_str = sched.get('NextRun', '')
            try:
                next_run = datetime.datetime.strptime(next_run_str, '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                next_run = None

            label = BodyLabel(f'  {tr(task_name, default=task_name)}')
            if next_run and next_run <= now:
                self._status_lists['queued'].addWidget(label)
            else:
                self._status_lists['waiting'].addWidget(label)

    # ── overview controls ───────────────────────────────────

    def _on_overview_start(self):
        self._do_save()
        self._ov_btn_start.setEnabled(False)
        self._ov_btn_stop.setEnabled(True)
        communicate.task_started.emit('__global__')
        logger.info('Scheduler started')
        self._refresh_overview()

    def _on_overview_stop(self):
        self._ov_btn_start.setEnabled(True)
        self._ov_btn_stop.setEnabled(False)
        self._running_task = None
        communicate.task_stopped.emit()
        logger.info('Scheduler stopped')
        self._refresh_overview()

    # ── signals ────────────────────────────────────────────

    def _connect_signals(self):
        self._tab_bar.config_switch.connect(self._on_switch_config)
        self._tab_bar.config_new.connect(self._on_new_config)
        self._tab_bar.config_copy.connect(self._on_copy_config)
        self._tab_bar.config_delete.connect(self._on_delete_config)
        self._tab_bar.config_export.connect(self._on_export_config)
        self._tab_bar.config_import.connect(self._on_import_config)

        communicate.new_log.connect(self._on_new_log)
        communicate.log.connect(self._on_log)
        communicate.new_frame.connect(self._on_new_frame)
        communicate.new_boxes.connect(self._on_new_boxes)
        communicate.clear_boxes.connect(lambda: self._screenshot_viewer.clear())
        communicate.task_started.connect(self._on_task_started)
        communicate.task_stopped.connect(self._on_task_stopped)

    # ── config management ──────────────────────────────────

    def _on_switch_config(self, name):
        if not name or name == self.config_name:
            return
        self._do_save()
        self.config_name = name
        self._al_config = AlConfig(name)
        self._args_data = self._load_args_json()
        self._load_all_tabs()

    def _on_new_config(self, name):
        dst = filepath_config(name)
        if os.path.exists(dst):
            from qfluentwidgets import InfoBar
            InfoBar.warning(tr('Error'), f'{tr("Config Name")} "{name}" ' + tr('exists'), parent=self)
            return
        write_file(dst, copy.deepcopy(self._al_config.data))
        self._tab_bar.add_tab(name)
        self._refresh_list()
        self._on_switch_config(name)

    def _on_copy_config(self, name):
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, tr('Duplicate Config'), tr('Config Name') + ':',
            text=f'{name}_copy')
        if ok and new_name.strip():
            src = filepath_config(name)
            dst = filepath_config(new_name.strip())
            if os.path.exists(dst):
                from qfluentwidgets import InfoBar
                InfoBar.warning(tr('Error'), f'{tr("Config Name")} "{new_name}" ' + tr('exists'), parent=self)
                return
            shutil.copy2(src, dst)
            self._tab_bar.add_tab(new_name.strip())
            self._refresh_list()

    def _on_delete_config(self, name):
        if self._tab_bar._tab_bar.count() <= 1:
            return
        p = filepath_config(name)
        if os.path.exists(p):
            os.remove(p)
        self._tab_bar.remove_tab(name)
        self._refresh_list()
        first = self._tab_bar._tab_bar.tabData(0)
        if first:
            self._on_switch_config(first)

    def _on_export_config(self, name):
        path, _ = QFileDialog.getSaveFileName(
            self, tr('Export Config'), f'{name}.ntecfg',
            'NTECFG Files (*.ntecfg);;JSON Files (*.json)')
        if path:
            data = read_file(filepath_config(name))
            if data:
                write_file(path, data)

    def _on_import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('Import Config'), '',
            'NTECFG Files (*.ntecfg);;JSON Files (*.json)')
        if path:
            data = read_file(path)
            if data:
                name = os.path.splitext(os.path.basename(path))[0]
                write_file(filepath_config(name), data)
                self._tab_bar.add_tab(name)
                self._refresh_list()

    def _refresh_list(self):
        config_dir = os.path.normpath('./config')
        if os.path.isdir(config_dir):
            names = sorted(f[:-5] for f in os.listdir(config_dir)
                           if f.endswith('.json'))
            self._tab_bar.set_config_list(names)
            self._tab_bar.set_current(self.config_name)

    # ── task signal handlers ───────────────────────────────

    def _on_task_started(self, task_name):
        self._running_task = task_name
        self._refresh_overview()

    def _on_task_stopped(self):
        self._running_task = None
        self._refresh_overview()

    # ── logging / debug ────────────────────────────────────

    @Slot(str)
    def _on_new_log(self, msg):
        self._compact_log.append(msg)
        csb = self._compact_log.verticalScrollBar()
        csb.setValue(csb.maximum())

    @Slot(int, str)
    def _on_log(self, level, msg):
        colors = {10: '#888888', 20: '#aabbcc', 30: '#f0c040', 40: '#ff6644', 50: '#ff2222'}
        c = colors.get(level, '#aabbcc')
        self._compact_log.append(f'<span style="color:{c}">{msg}</span>')

    @Slot(object)
    def _on_new_frame(self, frame):
        if frame is not None:
            self._screenshot_viewer.set_image(frame)
            h, w = frame.shape[:2]
            self._debug_info_label.setText(f'{tr("Screenshot")}: {w}x{h}')

    @Slot(object)
    def _on_new_boxes(self, boxes):
        self._screenshot_viewer.set_boxes(boxes)

    # ── helpers ────────────────────────────────────────────

    def _do_save(self):
        self._al_config.save()

    # ── lifecycle ──────────────────────────────────────────

    def set_executor(self, executor):
        self.executor = executor

    @property
    def screenshot_viewer(self):
        return self._screenshot_viewer

    @property
    def log_view(self):
        return self._compact_log

    @property
    def debug_info_label(self):
        return self._debug_info_label

    def closeEvent(self, event):
        self._do_save()
        communicate.quit.emit()
        if self.executor:
            self.executor.stop()
        super().closeEvent(event)
