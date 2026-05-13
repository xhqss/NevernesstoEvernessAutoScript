"""
Main window for al-script GUI.
PySide6-based interface with task management, template viewer, debug tools, and settings.
"""

import json
import os
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QRect
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QTextEdit, QSplitter, QGroupBox, QFormLayout, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QScrollArea,
    QTabWidget, QMessageBox, QStatusBar, QMenuBar, QFileDialog,
    QFrame, QSizePolicy, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QToolBar, QDialog, QDialogButtonBox
)

from module.config import AlConfig, deep_get, deep_set
from module.config.utils import read_file, write_file, filepath_config
from module.gui.communicate import communicate
from module.gui.log_handler import GuiLogHandler
from module.gui.overlay import ScreenshotViewer
from module.util.logger import logger


# ====== Stylesheet ======
DARK_THEME = """
    QMainWindow { background-color: #1a1a2e; }
    QLabel { color: #ccccdd; }
    QGroupBox {
        color: #ccccdd;
        border: 1px solid #3d3d5c;
        border-radius: 6px;
        margin-top: 12px;
        padding: 15px;
        font-size: 13px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #8888cc;
    }
"""

SIDEBAR_STYLE = """
    #sidebar {
        background-color: #2b2b3d;
        border-right: 1px solid #3d3d5c;
    }
"""


class ConfigCard(QFrame):
    """A card widget for editing a config group."""

    def __init__(self, group_name, args_dict, task_name, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.args_dict = args_dict
        self.task_name = task_name
        self._widgets = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group_box = QGroupBox(self.group_name)
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(10, 15, 10, 10)

        for arg_name, arg_data in self.args_dict.items():
            if not isinstance(arg_data, dict):
                continue
            if arg_data.get('display') == 'hide':
                continue

            value = arg_data.get('value', '')
            options = arg_data.get('option', None)
            arg_type = arg_data.get('type', 'input')
            key = f'{self.task_name}.{self.group_name}.{arg_name}'

            widget = self._create_widget(arg_name, arg_data, key)
            if widget:
                if isinstance(widget, QCheckBox):
                    form.addRow(arg_name, widget)
                else:
                    label = QLabel(arg_name)
                    label.setStyleSheet('color: #9999bb; font-size: 12px;')
                    form.addRow(label, widget)

        group_box.setLayout(form)
        layout.addWidget(group_box)

    def _create_widget(self, arg_name, arg_data, key):
        value = arg_data.get('value', '')
        options = arg_data.get('option', None)
        arg_type = arg_data.get('type', 'input')

        if arg_type == 'checkbox' or isinstance(value, bool):
            cb = QCheckBox()
            cb.setChecked(bool(value))
            cb.stateChanged.connect(
                lambda checked, k=key: self._on_change(k, bool(checked))
            )
            return cb

        elif options:
            combo = QComboBox()
            combo.addItems([str(o) for o in options])
            idx = 0
            for i, o in enumerate(options):
                if str(o) == str(value):
                    idx = i
                    break
            combo.setCurrentIndex(idx)
            combo.currentTextChanged.connect(
                lambda text, k=key: self._on_change(k, text)
            )
            return combo

        elif arg_type == 'input' or isinstance(value, (int, float)):
            if isinstance(value, float):
                spinner = QDoubleSpinBox()
                spinner.setRange(0, 999999)
                spinner.setValue(float(value))
                spinner.valueChanged.connect(
                    lambda v, k=key: self._on_change(k, v)
                )
                return spinner
            elif isinstance(value, int):
                spinner = QSpinBox()
                spinner.setRange(0, 999999)
                spinner.setValue(int(value))
                spinner.valueChanged.connect(
                    lambda v, k=key: self._on_change(k, v)
                )
                return spinner
            else:
                line = QLineEdit(str(value) if value else '')
                line.textChanged.connect(
                    lambda text, k=key: self._on_change(k, text)
                )
                return line

        else:
            line = QLineEdit(str(value) if value else '')
            line.textChanged.connect(
                lambda text, k=key: self._on_change(k, text)
            )
            return line

    def _on_change(self, key, value):
        communicate.config_changed.emit()


class MainWindow(QMainWindow):
    """Main application window for al-script."""

    def __init__(self, config_name='template'):
        super().__init__()
        self.config_name = config_name
        self.config = AlConfig(config_name)
        self.executor = None
        self.task_thread = None
        self._boxes = []

        self._init_ui()
        self._connect_signals()
        self._load_task_list()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f'al-script - {self.config_name}')
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.setStyleSheet(DARK_THEME)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === Left Sidebar ===
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # === Right Content ===
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background-color: #1a1a2e; }
            QTabBar::tab {
                background-color: #222233; color: #8888aa;
                padding: 10px 24px; font-size: 13px; border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #ffffff; background-color: #1a1a2e;
                border-bottom: 2px solid #4a6cf7;
            }
            QTabBar::tab:hover { color: #ccccdd; }
        """)

        # Tab: Task Config
        self._create_task_config_tab()

        # Tab: Templates
        self._create_template_tab()

        # Tab: Debug
        self._create_debug_tab()

        # Tab: Log
        self._create_log_tab()

        # Tab: Settings
        self._create_settings_tab()

        # Tab: About
        self._create_about_tab()

        content_layout.addWidget(self.tabs)

        # Bottom bar
        self._create_bottom_bar(content_layout)

        main_layout.addWidget(content, 1)

    def _create_sidebar(self):
        """Create the left sidebar."""
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName('sidebar')
        sidebar.setStyleSheet(SIDEBAR_STYLE)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel('al-script')
        title.setStyleSheet('font-size: 18px; font-weight: bold; color: #ffffff; padding: 10px 0;')
        layout.addWidget(title)

        task_label = QLabel('Tasks')
        task_label.setStyleSheet('color: #8888aa; font-size: 11px; text-transform: uppercase;')
        layout.addWidget(task_label)

        self.task_list = QListWidget()
        self.task_list.setStyleSheet("""
            QListWidget {
                background-color: #222233; border: 1px solid #3d3d5c;
                border-radius: 4px; color: #ccccdd; font-size: 13px;
            }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #2a2a3d; }
            QListWidget::item:selected {
                background-color: #4a6cf7; color: #ffffff; border-radius: 4px;
            }
            QListWidget::item:hover { background-color: #33334d; }
        """)
        layout.addWidget(self.task_list)

        btn_style = """
            QPushButton { padding: 10px; border-radius: 6px; font-size: 13px;
            font-weight: bold; border: none; }
        """

        self.btn_start = QPushButton('Start')
        self.btn_start.setStyleSheet(btn_style + 'background-color: #22c55e; color: white;')
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton('Stop')
        self.btn_stop.setStyleSheet(btn_style + 'background-color: #ef4444; color: white;')
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop)

        self.btn_pause = QPushButton('Pause')
        self.btn_pause.setStyleSheet(btn_style + 'background-color: #f59e0b; color: white;')
        self.btn_pause.setEnabled(False)
        layout.addWidget(self.btn_pause)

        layout.addStretch()

        self.status_indicator = QLabel('Idle')
        self.status_indicator.setStyleSheet('color: #888888; font-size: 12px; padding: 5px;')
        layout.addWidget(self.status_indicator)

        return sidebar

    def _create_task_config_tab(self):
        """Create the task configuration tab."""
        self.config_scroll = QScrollArea()
        self.config_scroll.setWidgetResizable(True)
        self.config_scroll.setStyleSheet('background-color: #1a1a2e; border: none;')
        self.config_container = QWidget()
        self.config_layout = QVBoxLayout(self.config_container)
        self.config_layout.setSpacing(8)
        self.config_layout.setContentsMargins(20, 20, 20, 20)
        self.config_scroll.setWidget(self.config_container)
        self.tabs.addTab(self.config_scroll, 'Task Config')

    def _create_template_tab(self):
        """Create the template management tab."""
        template_widget = QWidget()
        template_layout = QVBoxLayout(template_widget)
        template_layout.setContentsMargins(20, 20, 20, 20)

        # Template list
        self.template_tree = QTreeWidget()
        self.template_tree.setHeaderLabels(['Name', 'Type', 'Size', 'Path'])
        self.template_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a2e; color: #ccccdd;
                border: 1px solid #3d3d5c; border-radius: 4px;
            }
            QTreeWidget::item { padding: 4px; }
            QTreeWidget::item:selected { background-color: #4a6cf7; }
            QHeaderView::section {
                background-color: #222233; color: #8888aa;
                padding: 6px; border: none; border-bottom: 1px solid #3d3d5c;
            }
        """)
        template_layout.addWidget(self.template_tree)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton('Refresh Templates')
        btn_refresh.setStyleSheet(self._btn_style('#4a6cf7'))
        btn_refresh.clicked.connect(self._refresh_templates)
        btn_layout.addWidget(btn_refresh)

        btn_import = QPushButton('Import PNG')
        btn_import.setStyleSheet(self._btn_style('#4a6cf7'))
        btn_import.clicked.connect(self._import_template)
        btn_layout.addWidget(btn_import)

        btn_layout.addStretch()
        template_layout.addLayout(btn_layout)
        template_layout.addStretch()

        self.tabs.addTab(template_widget, 'Templates')

    def _create_debug_tab(self):
        """Create the debug/screenshot preview tab."""
        debug_widget = QWidget()
        debug_layout = QVBoxLayout(debug_widget)
        debug_layout.setContentsMargins(20, 20, 20, 20)

        # Screenshot viewer
        self.screenshot_viewer = ScreenshotViewer()
        self.screenshot_viewer.setMinimumSize(640, 360)
        self.screenshot_viewer.setStyleSheet('border: 1px solid #3d3d5c; border-radius: 4px;')
        debug_layout.addWidget(self.screenshot_viewer)

        # Info bar
        info_layout = QHBoxLayout()
        self.debug_info_label = QLabel('No screenshot')
        self.debug_info_label.setStyleSheet('color: #8888aa; font-size: 12px;')
        info_layout.addWidget(self.debug_info_label)
        info_layout.addStretch()

        btn_screenshot = QPushButton('Take Screenshot')
        btn_screenshot.setStyleSheet(self._btn_style('#4a6cf7'))
        btn_screenshot.clicked.connect(self._take_debug_screenshot)
        info_layout.addWidget(btn_screenshot)

        btn_clear = QPushButton('Clear')
        btn_clear.setStyleSheet(self._btn_style('#666688'))
        btn_clear.clicked.connect(lambda: self.screenshot_viewer.clear())
        info_layout.addWidget(btn_clear)

        debug_layout.addLayout(info_layout)
        self.tabs.addTab(debug_widget, 'Debug')

    def _create_log_tab(self):
        """Create the log viewer tab."""
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a; color: #aabbcc;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px; border: none; padding: 10px;
            }
        """)
        self.tabs.addTab(self.log_view, 'Log')

    def _create_settings_tab(self):
        """Create the settings tab."""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(12)

        # General settings
        general_group = QGroupBox('General')
        general_form = QFormLayout()
        general_form.setSpacing(8)

        self.setting_theme = QComboBox()
        self.setting_theme.addItems(['Dark', 'Light'])
        general_form.addRow('Theme:', self.setting_theme)

        self.setting_language = QComboBox()
        self.setting_language.addItems(['English', '中文', '日本語'])
        general_form.addRow('Language:', self.setting_language)

        self.setting_auto_start = QCheckBox()
        general_form.addRow('Auto-start on launch:', self.setting_auto_start)

        general_group.setLayout(general_form)
        settings_layout.addWidget(general_group)

        # Debug settings
        debug_group = QGroupBox('Debug')
        debug_form = QFormLayout()
        debug_form.setSpacing(8)

        self.setting_use_overlay = QCheckBox()
        debug_form.addRow('Enable debug overlay:', self.setting_use_overlay)

        self.setting_show_logs_overlay = QCheckBox()
        debug_form.addRow('Show logs on overlay:', self.setting_show_logs_overlay)

        debug_group.setLayout(debug_form)
        settings_layout.addWidget(debug_group)

        # Paths
        paths_group = QGroupBox('Paths')
        paths_form = QFormLayout()
        paths_form.setSpacing(8)

        self.setting_config_dir = QLineEdit('./config')
        paths_form.addRow('Config directory:', self.setting_config_dir)

        self.setting_assets_dir = QLineEdit('./assets')
        paths_form.addRow('Assets directory:', self.setting_assets_dir)

        paths_group.setLayout(paths_form)
        settings_layout.addWidget(paths_group)

        settings_layout.addStretch()
        self.tabs.addTab(settings_widget, 'Settings')

    def _create_about_tab(self):
        """Create the about tab."""
        about_widget = QWidget()
        about_layout = QVBoxLayout(about_widget)
        about_layout.setContentsMargins(40, 40, 40, 40)
        about_layout.setSpacing(12)

        title = QLabel('al-script')
        title.setStyleSheet('font-size: 24px; font-weight: bold; color: #ffffff;')
        title.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(title)

        version = QLabel('Version 0.1.0')
        version.setStyleSheet('font-size: 14px; color: #8888aa;')
        version.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(version)

        desc = QLabel(
            'A universal game automation framework.\n'
            'Built from Alas (AzurLaneAutoScript) architecture\n'
            'with ok-script multi-platform design.'
        )
        desc.setStyleSheet('font-size: 13px; color: #aaaacc; line-height: 1.5;')
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        about_layout.addWidget(desc)

        about_layout.addStretch()

        copyright_label = QLabel('MIT License | Copyright 2024-2026')
        copyright_label.setStyleSheet('font-size: 11px; color: #666688;')
        copyright_label.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(copyright_label)

        self.tabs.addTab(about_widget, 'About')

    def _create_bottom_bar(self, parent_layout):
        """Create the bottom status bar."""
        btn_bar = QFrame()
        btn_bar.setStyleSheet('background-color: #222233; border-top: 1px solid #3d3d5c;')
        btn_bar_layout = QHBoxLayout(btn_bar)
        btn_bar_layout.setContentsMargins(15, 8, 15, 8)

        self.btn_save = QPushButton('Save Config')
        self.btn_save.setStyleSheet(self._btn_style('#4a6cf7'))
        btn_bar_layout.addWidget(self.btn_save)

        btn_bar_layout.addStretch()

        self.status_bar_label = QLabel('Ready')
        self.status_bar_label.setStyleSheet('color: #8888aa; font-size: 12px;')
        btn_bar_layout.addWidget(self.status_bar_label)

        parent_layout.addWidget(btn_bar)

    def _connect_signals(self):
        """Connect signals and slots."""
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_save.clicked.connect(self._on_save)
        self.task_list.currentItemChanged.connect(self._on_task_selected)

        communicate.new_log.connect(self._on_new_log)
        communicate.log.connect(self._on_log)
        communicate.new_frame.connect(self._on_new_frame)
        communicate.new_boxes.connect(self._on_new_boxes)
        communicate.new_status.connect(self._on_status_change)
        communicate.clear_boxes.connect(lambda: self.screenshot_viewer.clear())

    def _load_task_list(self):
        """Load task list from config."""
        self.task_list.clear()
        for task_name in self.config.get_task_list():
            item = QListWidgetItem(task_name)
            item.setData(Qt.UserRole, task_name)
            self.task_list.addItem(item)

        if self.task_list.count() > 0:
            self.task_list.setCurrentRow(0)

    def _on_task_selected(self, current, previous):
        """Handle task selection change."""
        if current is None:
            return
        task_name = current.data(Qt.UserRole)
        self._render_task_config(task_name)

    def _render_task_config(self, task_name):
        """Render configuration UI for a task."""
        while self.config_layout.count():
            item = self.config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        task_data = self.config.data.get(task_name, {})
        if not task_data:
            label = QLabel(f'No config for "{task_name}"')
            label.setStyleSheet('color: #8888aa; font-size: 14px; padding: 20px;')
            self.config_layout.addWidget(label)
            return

        for group_name, args in task_data.items():
            if group_name == 'Storage':
                continue
            if not isinstance(args, dict):
                continue
            card = ConfigCard(group_name, args, task_name)
            self.config_layout.addWidget(card)

        self.config_layout.addStretch()

    def _on_config_change(self, key, value):
        """Handle config value change."""
        deep_set(self.config.data, keys=key.split('.'), value=value)
        communicate.config_changed.emit()

    def _on_save(self):
        """Save config."""
        self.config.save()
        self.status_bar_label.setText('Config saved')
        communicate.config_saved.emit()
        QTimer.singleShot(3000, lambda: self.status_bar_label.setText('Ready'))

    def _on_start(self):
        """Start task execution."""
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_pause.setEnabled(True)
        self.status_indicator.setText('Running')
        self.status_indicator.setStyleSheet('color: #22c55e; font-size: 12px; padding: 5px;')
        communicate.task_started.emit(self.config_name)
        logger.info('Task started')

    def _on_stop(self):
        """Stop task execution."""
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.status_indicator.setText('Stopped')
        self.status_indicator.setStyleSheet('color: #ef4444; font-size: 12px; padding: 5px;')
        communicate.task_stopped.emit()
        logger.info('Task stopped')

    def _on_pause(self):
        """Toggle pause."""
        if self.btn_pause.text() == 'Pause':
            self.btn_pause.setText('Resume')
            self.status_indicator.setText('Paused')
            self.status_indicator.setStyleSheet('color: #f59e0b; font-size: 12px; padding: 5px;')
            communicate.task_paused.emit()
        else:
            self.btn_pause.setText('Pause')
            self.status_indicator.setText('Running')
            self.status_indicator.setStyleSheet('color: #22c55e; font-size: 12px; padding: 5px;')
            communicate.task_resumed.emit()

    @Slot(str)
    def _on_new_log(self, msg):
        """Append log message."""
        self.log_view.append(msg)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(int, str)
    def _on_log(self, level, msg):
        """Append log with level."""
        colors = {10: '#888888', 20: '#aabbcc', 30: '#f0c040', 40: '#ff6644', 50: '#ff2222'}
        color = colors.get(level, '#aabbcc')
        self.log_view.append(f'<span style="color:{color}">{msg}</span>')

    @Slot(object)
    def _on_new_frame(self, frame):
        """Display new screenshot frame."""
        if frame is not None:
            self.screenshot_viewer.set_image(frame)
            h, w = frame.shape[:2]
            self.debug_info_label.setText(f'Screenshot: {w}x{h}')

    @Slot(object)
    def _on_new_boxes(self, boxes):
        """Display new boxes on debug view."""
        self._boxes = boxes
        self.screenshot_viewer.set_boxes(boxes)

    @Slot(str)
    def _on_status_change(self, status):
        """Update status."""
        self.status_bar_label.setText(status)

    def _refresh_templates(self):
        """Refresh template list from assets directory."""
        self.template_tree.clear()
        assets_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
        if not os.path.isdir(assets_dir):
            return

        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                if file.endswith('.png') or file.endswith('.gif'):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, assets_dir)
                    size = os.path.getsize(path)
                    item = QTreeWidgetItem([
                        os.path.splitext(file)[0],
                        'Template' if file.startswith('TEMPLATE_') else 'Button',
                        f'{size / 1024:.1f} KB',
                        rel_path
                    ])
                    self.template_tree.addTopLevelItem(item)

    def _import_template(self):
        """Import a PNG file as a template."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Template', '', 'PNG Images (*.png);;All Files (*)'
        )
        if path:
            dest_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'default', 'imported')
            os.makedirs(dest_dir, exist_ok=True)
            import shutil
            dest = os.path.join(dest_dir, os.path.basename(path))
            shutil.copy2(path, dest)
            logger.info(f'Imported template: {dest}')
            self._refresh_templates()

    def _take_debug_screenshot(self):
        """Take a screenshot for debugging."""
        communicate.task_started.emit('debug_screenshot')

    @staticmethod
    def _btn_style(color):
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                padding: 8px 20px; border-radius: 4px;
                font-size: 13px; border: none;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """

    def set_executor(self, executor):
        """Set the task executor."""
        self.executor = executor

    def closeEvent(self, event):
        """Handle window close."""
        communicate.quit.emit()
        if self.executor:
            self.executor.stop()
        super().closeEvent(event)
