"""
Custom widgets for the al-script GUI.
- Switch: animated iOS-style toggle switch (replaces QCheckBox)
- ConfigCardV2: collapsible card for config groups
- KeyCaptureButton: button that listens for a key press
- KeyCaptureDialog: modal dialog for key rebinding
"""

from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QVariantAnimation, QEasingCurve, Signal, QTimer
from PySide6.QtGui import QPainter, QBrush, QColor, QPen, QFont, QKeyEvent, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import (
    QWidget, QCheckBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGroupBox, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QDialog, QDialogButtonBox, QApplication
)

from module.i18n import tr


# ═══════════════════════════════════════════════
#  Switch — animated toggle
# ═══════════════════════════════════════════════

class Switch(QCheckBox):
    """Animated iOS-style toggle switch. Drop-in replacement for QCheckBox."""

    def __init__(self, parent=None, width=44, height=24):
        super().__init__(parent)
        self._switch_width = width
        self._switch_height = height
        self._knob_margin = 3
        self._knob_size = height - 2 * self._knob_margin
        self._offset = 0.0  # 0 = off, 1 = on
        self._anim = None
        self.setFixedSize(width + 40, height + 4)  # extra width for label
        self.setCursor(Qt.PointingHandCursor)
        self.stateChanged.connect(self._animate)

    def _animate(self, checked):
        target = 1.0 if checked else 0.0
        if self._anim:
            self._anim.stop()
        self._anim = QVariantAnimation()
        self._anim.setDuration(200)
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.valueChanged.connect(self._set_offset)
        self._anim.start()

    def _set_offset(self, val):
        self._offset = val
        self.update()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Track
        track_rect = QRect(0, 2, self._switch_width, self._switch_height)
        track_radius = self._switch_height // 2

        if self.isChecked():
            track_color = QColor('#4a6cf7')
        else:
            track_color = QColor('#555566')

        p.setBrush(QBrush(track_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(track_rect, track_radius, track_radius)

        # Knob
        travel = self._switch_width - self._knob_size - 2 * self._knob_margin
        knob_x = self._knob_margin + int(travel * self._offset)
        knob_y = 2 + self._knob_margin
        knob_rect = QRect(knob_x, knob_y, self._knob_size, self._knob_size)

        p.setBrush(QBrush(QColor('#ffffff')))
        p.drawEllipse(knob_rect)

        # Label text
        text_rect = QRect(self._switch_width + 8, 0, 40, self._switch_height + 4)
        p.setPen(QColor('#ccccdd'))
        font = QFont()
        font.setPixelSize(12)
        p.setFont(font)
        p.drawText(text_rect, Qt.AlignVCenter, self.text())

        p.end()

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(self._switch_width + 80, self._switch_height + 4)


# ═══════════════════════════════════════════════
#  ConfigCardV2 — collapsible config card
# ═══════════════════════════════════════════════

class ConfigCardV2(QFrame):
    """Collapsible card widget for editing a config group.
    Uses Switch for booleans, SpinBox for numbers, ComboBox for options."""

    changed = Signal()

    def __init__(self, group_name: str, args_dict: dict, task_name: str,
                 gui_labels: dict = None, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.args_dict = args_dict
        self.task_name = task_name
        self.gui_labels = gui_labels or {}
        self._widgets: dict[str, QWidget] = {}
        self._collapsed = False
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 8)
        main_layout.setSpacing(0)

        # Group box as card
        display_name = self.gui_labels.get(self.group_name, self.group_name)
        group_box = QGroupBox(display_name)
        group_box.setCheckable(False)

        self._form_layout = QFormLayout()
        self._form_layout.setSpacing(8)
        self._form_layout.setContentsMargins(14, 18, 14, 12)

        for arg_name, arg_data in self.args_dict.items():
            if not isinstance(arg_data, dict):
                continue
            if arg_data.get('display') == 'hide' or arg_data.get('display') == 'disabled':
                continue

            widget = self._create_widget(arg_name, arg_data)
            if widget is None:
                continue

            # Translate the label
            label_text = self.gui_labels.get(arg_name, arg_name)
            label = QLabel(label_text)
            label.setStyleSheet('font-size: 12px;')
            label.setMinimumWidth(120)

            if isinstance(widget, Switch):
                widget.setText('')
                self._form_layout.addRow(label_text, widget)
            else:
                self._form_layout.addRow(label, widget)

        group_box.setLayout(self._form_layout)
        main_layout.addWidget(group_box)

    def _create_widget(self, arg_name: str, arg_data: dict) -> QWidget | None:
        value = arg_data.get('value', '')
        options = arg_data.get('option', None)
        arg_type = arg_data.get('type', '')
        key = f'{self.task_name}.{self.group_name}.{arg_name}'

        # Boolean → Switch
        if arg_type == 'checkbox' or isinstance(value, bool):
            sw = Switch()
            sw.setChecked(bool(value))
            sw.stateChanged.connect(
                lambda checked, k=key: self._on_change(k, bool(checked))
            )
            self._widgets[key] = sw
            return sw

        # Options → ComboBox
        if options:
            combo = QComboBox()
            str_options = [str(o) for o in options]
            combo.addItems(str_options)
            try:
                idx = str_options.index(str(value))
            except ValueError:
                idx = 0
            combo.setCurrentIndex(idx)
            combo.currentTextChanged.connect(
                lambda text, k=key: self._on_change(k, text)
            )
            self._widgets[key] = combo
            return combo

        # Float → DoubleSpinBox
        if isinstance(value, float):
            spin = QDoubleSpinBox()
            spin.setRange(0, 999999)
            spin.setDecimals(4)
            spin.setValue(float(value))
            spin.valueChanged.connect(
                lambda v, k=key: self._on_change(k, v)
            )
            self._widgets[key] = spin
            return spin

        # Int → SpinBox
        if isinstance(value, int):
            spin = QSpinBox()
            spin.setRange(0, 999999)
            spin.setValue(int(value))
            spin.valueChanged.connect(
                lambda v, k=key: self._on_change(k, v)
            )
            self._widgets[key] = spin
            return spin

        # Default → LineEdit
        line = QLineEdit(str(value) if value is not None else '')
        line.textChanged.connect(
            lambda text, k=key: self._on_change(k, text)
        )
        self._widgets[key] = line
        return line

    def _on_change(self, key, value):
        self.changed.emit()
        # Store the config path and value so main window can pick it up
        self._pending_key = key
        self._pending_value = value

    def get_changes(self) -> list[tuple[str, object]]:
        """Return list of (key, value) pending changes."""
        results = []
        for key, w in self._widgets.items():
            if isinstance(w, Switch):
                results.append((key, w.isChecked()))
            elif isinstance(w, QComboBox):
                results.append((key, w.currentText()))
            elif isinstance(w, QDoubleSpinBox):
                results.append((key, w.value()))
            elif isinstance(w, QSpinBox):
                results.append((key, w.value()))
            elif isinstance(w, QLineEdit):
                results.append((key, w.text()))
        return results


# ═══════════════════════════════════════════════
#  KeyCaptureDialog — modal key rebinding
# ═══════════════════════════════════════════════

class KeyCaptureDialog(QDialog):
    """Modal dialog that captures a single key press."""

    key_captured = Signal(str)

    # Human-readable key name mapping
    _KEY_NAMES = {
        Qt.Key_Escape: 'esc', Qt.Key_Tab: 'tab', Qt.Key_Backtab: 'tab',
        Qt.Key_Backspace: 'backspace', Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter',
        Qt.Key_Insert: 'insert', Qt.Key_Delete: 'delete', Qt.Key_Pause: 'pause',
        Qt.Key_Print: 'print', Qt.Key_SysReq: 'sysreq', Qt.Key_Clear: 'clear',
        Qt.Key_Home: 'home', Qt.Key_End: 'end', Qt.Key_Left: 'left',
        Qt.Key_Up: 'up', Qt.Key_Right: 'right', Qt.Key_Down: 'down',
        Qt.Key_PageUp: 'pageup', Qt.Key_PageDown: 'pagedown',
        Qt.Key_Shift: 'shift', Qt.Key_Control: 'ctrl', Qt.Key_Meta: 'meta',
        Qt.Key_Alt: 'alt', Qt.Key_AltGr: 'altgr', Qt.Key_CapsLock: 'capslock',
        Qt.Key_NumLock: 'numlock', Qt.Key_ScrollLock: 'scrolllock',
        Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3', Qt.Key_F4: 'f4',
        Qt.Key_F5: 'f5', Qt.Key_F6: 'f6', Qt.Key_F7: 'f7', Qt.Key_F8: 'f8',
        Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
        Qt.Key_Space: 'space',
    }

    def __init__(self, current_key: str = '', parent=None):
        super().__init__(parent)
        self._captured = current_key
        self._init_ui(current_key)

    def _init_ui(self, current_key: str):
        self.setWindowTitle(tr('Key Binding'))
        self.setFixedSize(320, 180)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._prompt = QLabel(tr('Press a key to bind...'))
        self._prompt.setAlignment(Qt.AlignCenter)
        self._prompt.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(self._prompt)

        self._key_display = QLabel(current_key or tr('(none)'))
        self._key_display.setAlignment(Qt.AlignCenter)
        self._key_display.setStyleSheet(
            'font-size: 24px; font-weight: bold; padding: 12px; '
            'border: 2px dashed #4a6cf7; border-radius: 8px; min-height: 40px;'
        )
        layout.addWidget(self._key_display)

        btn_layout = QHBoxLayout()
        self._clear_btn = QPushButton(tr('Clear'))
        self._clear_btn.clicked.connect(lambda: self._done(''))
        btn_layout.addWidget(self._clear_btn)
        btn_layout.addStretch()
        self._ok_btn = QPushButton(tr('OK'))
        self._ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._ok_btn)
        layout.addLayout(btn_layout)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_Escape:
            return super().keyPressEvent(event)

        name = self._key_to_name(key, event)
        self._captured = name
        self._key_display.setText(name)
        self._key_display.setStyleSheet(
            'font-size: 24px; font-weight: bold; padding: 12px; '
            'border: 2px solid #22c55e; border-radius: 8px; min-height: 40px;'
        )
        self._prompt.setText(tr('Key captured! Click OK or press another key.'))

    def _key_to_name(self, key: int, event: QKeyEvent) -> str:
        # Modifier + regular key
        parts = []
        if event.modifiers() & Qt.ControlModifier:
            parts.append('ctrl')
        if event.modifiers() & Qt.AltModifier:
            parts.append('alt')
        if event.modifiers() & Qt.ShiftModifier:
            parts.append('shift')

        if key in self._KEY_NAMES:
            parts.append(self._KEY_NAMES[key])
        elif Qt.Key_A <= key <= Qt.Key_Z:
            parts.append(chr(key).lower())
        elif Qt.Key_0 <= key <= Qt.Key_9:
            parts.append(chr(key))
        elif Qt.Key_F1 <= key <= Qt.Key_F35:
            parts.append(f'f{key - Qt.Key_F1 + 1}')
        else:
            parts.append(event.text().lower() or f'key({key})')

        return '+'.join(parts) if len(parts) > 1 else parts[0]

    def _done(self, key: str):
        self._captured = key
        self.accept()

    def captured_key(self) -> str:
        return self._captured


# ═══════════════════════════════════════════════
#  SectionHeader — collapsible section label
# ═══════════════════════════════════════════════

class SectionHeader(QPushButton):
    """Clickable section header for sidebar grouping."""

    toggled = Signal(bool)

    def __init__(self, text: str, expanded: bool = True, parent=None):
        super().__init__(text, parent)
        self._expanded = expanded
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            'QPushButton { text-align: left; padding: 8px 12px; '
            'font-size: 11px; font-weight: bold; text-transform: uppercase; '
            'border: none; background: transparent; }'
        )
        self.clicked.connect(self._toggle)

    def _toggle(self):
        self._expanded = not self._expanded
        self.toggled.emit(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded
