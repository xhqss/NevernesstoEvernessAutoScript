"""
Main window for NevernesstoEvernessAutoScript GUI.
v2.0 — OKLCH dynamic theme, auto-save, Explorer toolbar, card-based config.

This is the shell that wires together: sidebar, toolbar, tabs, ConfigManager,
TaskConfigTab, and the communication bus. Heavy logic lives in config_manager.py
and task_config_tab.py.
"""

import os
import sys
import shutil

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QTextEdit, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QScrollArea, QTabWidget,
    QFileDialog, QFrame, QTreeWidget, QTreeWidgetItem, QDockWidget,
)

from module.gui.communicate import communicate
from module.gui.overlay import ScreenshotViewer
from module.gui.theme import get_theme
from module.gui.toolbar import ExplorerToolbar
from module.gui.instance_panel import InstancePanel
from module.gui.config_manager import ConfigManager
from module.gui.task_config_tab import TaskConfigTab
from module.i18n import translator, set_language
from module.i18n import tr as _tr
from module.util.logger import logger


def tr(key, default=None):
    return _tr(key, default)


class MainWindow(QMainWindow):
    """v2.0 — Modernized main window."""

    def __init__(self, config=None):
        super().__init__()
        if isinstance(config, str):
            self._full_config = {}
            self.config_name = config
        else:
            self.config = config or {}
            self.config_name = self.config.get('config_name', 'template')
            self._full_config = config

        # Central managers
        self._cm = ConfigManager(self.config_name)
        self._theme = get_theme()
        self._theme_mode = 'dark'
        self._current_lang = 'zh_CN'

        self.executor = None
        self._boxes = []

        self._init_ui()
        self._init_task_tab()
        self._connect_signals()
        self._cm.set_unsaved_dot(self._unsaved_dot)
        self._cm.set_status_label(self.status_bar_label)
        self._cm.set_config_changed_callback(self._on_config_name_changed)
        self._task_tab.load_tasks()
        self._apply_language_from_config()
        self._apply_theme()

    # ═══════════════════════════════════════════════
    #  Theme / Language
    # ═══════════════════════════════════════════════

    def _apply_theme(self):
        app = QApplication.instance()
        if app:
            app.setStyleSheet(self._theme.generate_qss())

    def _switch_theme(self, mode: str):
        self._theme_mode = mode
        self._theme.mode = mode
        self._apply_theme()
        communicate.theme_changed.emit(mode)

    def _apply_language_from_config(self):
        lang = 'zh_CN'
        import locale
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang and sys_lang.startswith('zh'):
                lang = 'zh_CN'
        except Exception:
            pass
        self._switch_language(lang)
        if hasattr(self, 'setting_language'):
            idx = 0 if lang == 'en' else 1
            self.setting_language.blockSignals(True)
            self.setting_language.setCurrentIndex(idx)
            self.setting_language.blockSignals(False)

    # ═══════════════════════════════════════════════
    #  UI Construction
    # ═══════════════════════════════════════════════

    def _init_ui(self):
        gui_title = self._full_config.get('gui_title', 'al-script')
        self.setWindowTitle(f'{gui_title} - {self.config_name}')
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        self._toolbar = ExplorerToolbar(config_name=self.config_name)
        main_layout.addWidget(self._toolbar)

        # Body: sidebar + content
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._create_sidebar())
        body_layout.addWidget(self._create_content(), 1)
        main_layout.addWidget(body, 1)

        # Bottom bar
        self._create_bottom_bar(main_layout)

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName('sidebar')

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        gui_title = self._full_config.get('gui_title', 'al-script')
        title = QLabel(gui_title)
        title.setStyleSheet('font-size: 17px; font-weight: bold; padding: 8px 0;')
        layout.addWidget(title)

        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet('border-color: rgba(128,128,160,0.2);')
        layout.addWidget(d)

        task_header = QLabel(tr('Tasks'))
        task_header.setStyleSheet('font-size: 11px; text-transform: uppercase; padding: 4px 0;')
        layout.addWidget(task_header)

        self.task_list = QListWidget()
        self.task_list.setStyleSheet('QListWidget { border: none; outline: none; }')
        layout.addWidget(self.task_list)
        layout.addSpacing(8)

        self.btn_start = QPushButton(tr('Start'))
        self.btn_start.setObjectName('btn_start')
        layout.addWidget(self.btn_start)
        self.btn_stop = QPushButton(tr('Stop'))
        self.btn_stop.setObjectName('btn_stop')
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop)
        self.btn_pause = QPushButton(tr('Pause'))
        self.btn_pause.setObjectName('btn_pause')
        self.btn_pause.setEnabled(False)
        layout.addWidget(self.btn_pause)
        layout.addStretch()

        self.status_indicator = QLabel(tr('Idle'))
        self.status_indicator.setStyleSheet('font-size: 12px; padding: 5px;')
        layout.addWidget(self.status_indicator)
        return sidebar

    def _create_content(self):
        self.tabs = QTabWidget()
        self._create_task_config_tab()
        self._create_template_tab()
        self._create_debug_tab()
        self._create_log_tab()
        self._create_settings_tab()
        self._create_about_tab()
        return self.tabs

    def _init_task_tab(self):
        self._task_tab = TaskConfigTab(
            self._cm, self.task_list, self.config_scroll,
            self.config_container, self.config_layout
        )
        self._cm.set_config_cards(self._task_tab.cards())

    def _create_task_config_tab(self):
        self.config_scroll = QScrollArea()
        self.config_scroll.setWidgetResizable(True)
        self.config_container = QWidget()
        self.config_layout = QVBoxLayout(self.config_container)
        self.config_layout.setSpacing(4)
        self.config_layout.setContentsMargins(20, 20, 20, 20)
        self.config_scroll.setWidget(self.config_container)
        self.tabs.addTab(self.config_scroll, tr('Task Config'))

    def _create_template_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        self.template_tree = QTreeWidget()
        self.template_tree.setHeaderLabels([tr('Name'), tr('Type'), tr('Size'), tr('Path')])
        layout.addWidget(self.template_tree)

        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton(tr('Refresh Templates'))
        btn_refresh.clicked.connect(self._refresh_templates)
        btn_layout.addWidget(btn_refresh)
        btn_import = QPushButton(tr('Import PNG'))
        btn_import.clicked.connect(self._import_template)
        btn_layout.addWidget(btn_import)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        self.tabs.addTab(w, tr('Templates'))

    def _create_debug_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        self.screenshot_viewer = ScreenshotViewer()
        self.screenshot_viewer.setMinimumSize(640, 360)
        layout.addWidget(self.screenshot_viewer)

        info_layout = QHBoxLayout()
        self.debug_info_label = QLabel(tr('No screenshot'))
        info_layout.addWidget(self.debug_info_label)
        info_layout.addStretch()
        btn_screenshot = QPushButton(tr('Take Screenshot'))
        btn_screenshot.clicked.connect(lambda: communicate.task_started.emit('debug_screenshot'))
        info_layout.addWidget(btn_screenshot)
        btn_clear = QPushButton(tr('Clear'))
        btn_clear.clicked.connect(lambda: self.screenshot_viewer.clear())
        info_layout.addWidget(btn_clear)
        layout.addLayout(info_layout)
        self.tabs.addTab(w, tr('Debug'))

    def _create_log_tab(self):
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName('logView')
        self.tabs.addTab(self.log_view, tr('Log'))

    def _create_settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # General
        g = QGroupBox(tr('General'))
        f = QFormLayout()
        f.setSpacing(10)
        self.setting_theme = QComboBox()
        self.setting_theme.addItems([tr('Dark Mode'), tr('Light Mode')])
        f.addRow(tr('Theme') + ':', self.setting_theme)
        self.setting_language = QComboBox()
        self.setting_language.addItems(['English', '中文'])
        self.setting_language.setCurrentIndex(1)
        f.addRow(tr('Language') + ':', self.setting_language)
        self.setting_auto_start = QCheckBox()
        f.addRow(tr('Auto-start on launch') + ':', self.setting_auto_start)
        g.setLayout(f)
        layout.addWidget(g)

        # Debug
        dg = QGroupBox(tr('Debug'))
        df = QFormLayout()
        df.setSpacing(10)
        self.setting_use_overlay = QCheckBox()
        df.addRow(tr('Enable debug overlay') + ':', self.setting_use_overlay)
        self.setting_show_logs_overlay = QCheckBox()
        df.addRow(tr('Show logs on overlay') + ':', self.setting_show_logs_overlay)
        dg.setLayout(df)
        layout.addWidget(dg)

        # Paths
        pg = QGroupBox(tr('Paths'))
        pf = QFormLayout()
        pf.setSpacing(10)
        self.setting_config_dir = QLineEdit('./config')
        pf.addRow(tr('Config directory') + ':', self.setting_config_dir)
        self.setting_assets_dir = QLineEdit('./assets')
        pf.addRow(tr('Assets directory') + ':', self.setting_assets_dir)
        pg.setLayout(pf)
        layout.addWidget(pg)
        layout.addStretch()
        self.tabs.addTab(w, tr('Settings'))

    def _create_about_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)
        gui_title = self._full_config.get('gui_title', 'al-script')
        t = QLabel(gui_title)
        t.setStyleSheet('font-size: 24px; font-weight: bold;')
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)
        v = QLabel(f'{tr("Version")} {self._full_config.get("version", "0.1.0")}')
        v.setStyleSheet('font-size: 14px;')
        v.setAlignment(Qt.AlignCenter)
        layout.addWidget(v)
        layout.addStretch()
        c = QLabel('MIT License | Copyright 2024-2026')
        c.setStyleSheet('font-size: 11px;')
        c.setAlignment(Qt.AlignCenter)
        layout.addWidget(c)
        self.tabs.addTab(w, tr('About'))

    def _create_bottom_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName('bottomBar')
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(15, 6, 15, 6)
        self._unsaved_dot = QLabel('')
        self._unsaved_dot.setFixedSize(10, 10)
        self._unsaved_dot.setStyleSheet('background-color: #f59e0b; border-radius: 5px;')
        self._unsaved_dot.setVisible(False)
        self._unsaved_dot.setToolTip(tr('Unsaved changes'))
        bar_layout.addWidget(self._unsaved_dot)
        self.status_bar_label = QLabel(tr('Ready'))
        self.status_bar_label.setObjectName('statusBar')
        bar_layout.addWidget(self.status_bar_label)
        bar_layout.addStretch()
        self._runtime_label = QLabel('')
        self._runtime_label.setObjectName('statusBar')
        bar_layout.addWidget(self._runtime_label)
        parent_layout.addWidget(bar)

    # ═══════════════════════════════════════════════
    #  Signals
    # ═══════════════════════════════════════════════

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_pause.clicked.connect(self._on_pause)
        self.setting_theme.currentTextChanged.connect(self._on_theme_changed)
        self.setting_language.currentTextChanged.connect(self._on_language_changed)

        # Toolbar → ConfigManager
        self._toolbar.config_switch.connect(self._cm.switch_config)
        self._toolbar.config_new.connect(lambda n: (self._cm.new_config(n), self._refresh_config_list()))
        self._toolbar.config_save.connect(lambda n: (self._cm.save_as(n), self._refresh_config_list()))
        self._toolbar.config_delete.connect(lambda n: (self._cm.delete_config(n), self._refresh_config_list()))
        self._toolbar.config_export.connect(lambda n: self._cm.export_config(n, self))
        self._toolbar.config_import.connect(lambda: (self._cm.import_config(self), self._refresh_config_list()))
        self._toolbar.config_refresh.connect(self._refresh_config_list)
        self._toolbar.open_config_dir.connect(self._cm.open_config_dir)
        self._toolbar.multi_instance.connect(self._show_instance_panel)

        # Communication bus
        communicate.new_log.connect(self._on_new_log)
        communicate.log.connect(self._on_log)
        communicate.new_frame.connect(self._on_new_frame)
        communicate.new_boxes.connect(self._on_new_boxes)
        communicate.new_status.connect(self._on_status_change)
        communicate.clear_boxes.connect(lambda: self.screenshot_viewer.clear())
        communicate.config_changed.connect(self._cm.on_external_config_change)

    # ═══════════════════════════════════════════════
    #  Config name changed callback
    # ═══════════════════════════════════════════════

    def _on_config_name_changed(self, name):
        gui_title = self._full_config.get('gui_title', 'al-script')
        self.setWindowTitle(f'{gui_title} - {name}')
        self._refresh_config_list()
        self._task_tab.load_tasks()

    def _refresh_config_list(self):
        names = self._cm.scan_configs()
        self._toolbar.set_config_list(names)
        self._toolbar.set_current(self._cm.config_name)

    # ═══════════════════════════════════════════════
    #  Theme / Language switching
    # ═══════════════════════════════════════════════

    def _on_theme_changed(self, text):
        mode_map = {tr('Dark Mode'): 'dark', tr('Light Mode'): 'light',
                     'Dark Mode': 'dark', 'Light Mode': 'light'}
        self._switch_theme(mode_map.get(text, 'dark'))

    def _on_language_changed(self, text):
        lang_map = {'English': 'en', '中文': 'zh_CN'}
        self._switch_language(lang_map.get(text, 'zh_CN'))

    def _switch_language(self, lang):
        set_language(lang)
        self._current_lang = lang
        self._refresh_ui_text()

    def _refresh_ui_text(self):
        self.btn_start.setText(tr('Start'))
        self.btn_stop.setText(tr('Stop'))
        self.btn_pause.setText(tr('Pause'))
        self._task_tab.refresh_task_labels()
        tab_labels = [tr('Task Config'), tr('Templates'), tr('Debug'),
                      tr('Log'), tr('Settings'), tr('About')]
        for i, label in enumerate(tab_labels):
            self.tabs.setTabText(i, label)
        current = self.status_indicator.text()
        if current in (tr('Idle'), 'Idle', '空闲'):
            self.status_indicator.setText(tr('Idle'))
        elif current in (tr('Running'), 'Running', '运行中'):
            self.status_indicator.setText(tr('Running'))
        elif current in (tr('Stopped'), 'Stopped', '已停止'):
            self.status_indicator.setText(tr('Stopped'))
        elif current in (tr('Paused'), 'Paused', '已暂停'):
            self.status_indicator.setText(tr('Paused'))
        self._task_tab.re_render()

    # ═══════════════════════════════════════════════
    #  Task execution
    # ═══════════════════════════════════════════════

    def _on_start(self):
        task_name = self._task_tab.selected_task_name()
        if not task_name:
            return
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText(tr('Pause'))
        self.status_indicator.setText(tr('Running'))
        self.status_indicator.setStyleSheet('color: #22c55e; font-size: 12px; padding: 5px;')
        self.status_bar_label.setText(tr('Task started'))
        communicate.task_started.emit(task_name)
        logger.info(f'Task started: {task_name}')

    def _on_stop(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.status_indicator.setText(tr('Stopped'))
        self.status_indicator.setStyleSheet('color: #ef4444; font-size: 12px; padding: 5px;')
        communicate.task_stopped.emit()
        logger.info('Task stopped')

    def _on_pause(self):
        if self.btn_pause.text() in (tr('Pause'), 'Pause'):
            self.btn_pause.setText(tr('Resume'))
            self.status_indicator.setText(tr('Paused'))
            self.status_indicator.setStyleSheet('color: #f59e0b; font-size: 12px; padding: 5px;')
            communicate.task_paused.emit()
        else:
            self.btn_pause.setText(tr('Pause'))
            self.status_indicator.setText(tr('Running'))
            self.status_indicator.setStyleSheet('color: #22c55e; font-size: 12px; padding: 5px;')
            communicate.task_resumed.emit()

    # ═══════════════════════════════════════════════
    #  Multi-instance panel
    # ═══════════════════════════════════════════════

    def _show_instance_panel(self):
        for child in self.findChildren(QDockWidget):
            if child.windowTitle() == tr('Multi-Instance Manager'):
                child.close()
                child.deleteLater()
        dock = QDockWidget(tr('Multi-Instance Manager'), self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        panel = InstancePanel(config_dir='./config')
        panel.instance_start.connect(lambda n: logger.info(f'Start instance: {n}'))
        panel.instance_stop.connect(lambda n: logger.info(f'Stop instance: {n}'))
        panel.instance_restart.connect(lambda n: logger.info(f'Restart instance: {n}'))
        panel.instance_stop_all.connect(lambda: logger.info('Stop all instances'))
        panel.multi_launch.connect(lambda cn, cnt: [self._cm.new_config(f'{cn}_{i:02d}') for i in range(1, cnt + 1)])
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setFloating(False)

    # ═══════════════════════════════════════════════
    #  Logging / Debug
    # ═══════════════════════════════════════════════

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
        self._boxes = boxes
        self.screenshot_viewer.set_boxes(boxes)

    @Slot(str)
    def _on_status_change(self, status):
        self.status_bar_label.setText(status)

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
                    item = QTreeWidgetItem([
                        os.path.splitext(file)[0],
                        tr('Template') if file.startswith('TEMPLATE_') else tr('Button'),
                        f'{sz / 1024:.1f} KB', rel
                    ])
                    self.template_tree.addTopLevelItem(item)

    def _import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Import PNG'), '',
                                               'PNG Images (*.png);;All Files (*)')
        if path:
            dest_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'default', 'imported')
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(path))
            shutil.copy2(path, dest)
            logger.info(f'Imported template: {dest}')
            self._refresh_templates()

    # ═══════════════════════════════════════════════
    #  Lifecycle
    # ═══════════════════════════════════════════════

    def set_executor(self, executor):
        self.executor = executor

    def closeEvent(self, event):
        if self._unsaved_dot.isVisible():
            self._cm.flush_pending()
        communicate.quit.emit()
        if self.executor:
            self.executor.stop()
        super().closeEvent(event)
