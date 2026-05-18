"""
OKLCH dynamic theme system with automatic contrast calculation.
Produces WCAG-compliant dark/light QSS stylesheets from a few base parameters.
"""

import math


# ═══════════════════════════════════════════════
#  OKLCH ↔ sRGB conversion (perceptual color space)
# ═══════════════════════════════════════════════

def oklch_to_rgb(l: float, c: float, h: float) -> tuple[int, int, int]:
    """Convert OKLCH (L 0-1, C 0-0.4, H 0-360) to sRGB (0-255)."""
    # OKLCH → OKLab
    h_rad = math.radians(h)
    L = l
    a = c * math.cos(h_rad)
    b = c * math.sin(h_rad)

    # OKLab → Linear sRGB
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l3 = l_ * l_ * l_
    m3 = m_ * m_ * m_
    s3 = s_ * s_ * s_

    r_lin = +4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    g_lin = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    b_lin = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3

    # Linear → sRGB gamma
    def linear_to_srgb(c: float) -> float:
        if c <= 0.0031308:
            return 12.92 * c
        return 1.055 * (c ** (1.0 / 2.4)) - 0.055

    r = max(0, min(255, round(linear_to_srgb(r_lin) * 255)))
    g = max(0, min(255, round(linear_to_srgb(g_lin) * 255)))
    b = max(0, min(255, round(linear_to_srgb(b_lin) * 255)))
    return (r, g, b)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f'#{r:02x}{g:02x}{b:02x}'


def oklch_to_hex(l: float, c: float, h: float) -> str:
    return rgb_to_hex(*oklch_to_rgb(l, c, h))


# ═══════════════════════════════════════════════
#  WCAG contrast / relative luminance
# ═══════════════════════════════════════════════

def _srgb_linearize(channel_8bit: float) -> float:
    c = channel_8bit / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(r: int, g: int, b: int) -> float:
    return (
        0.2126 * _srgb_linearize(r) +
        0.7152 * _srgb_linearize(g) +
        0.0722 * _srgb_linearize(b)
    )


def contrast_ratio(bg: tuple[int, int, int], fg: tuple[int, int, int]) -> float:
    l1 = relative_luminance(*bg)
    l2 = relative_luminance(*fg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def best_text_color(bg_rgb: tuple[int, int, int]) -> str:
    """Return white (#ffffff) or black (#000000) based on WCAG contrast."""
    w_contrast = contrast_ratio(bg_rgb, (255, 255, 255))
    b_contrast = contrast_ratio(bg_rgb, (0, 0, 0))
    if w_contrast >= b_contrast and w_contrast >= 4.5:
        return '#ffffff'
    return '#000000'


# ═══════════════════════════════════════════════
#  Golden-ratio harmony helpers
# ═══════════════════════════════════════════════

GOLDEN_ANGLE = 137.507764  # degrees — the "most irrational" hue step
PHI = 1.618033988749895


def golden_shift_hue(base_hue: float, steps: int = 1) -> float:
    """Rotate hue by golden-angle steps for visually harmonious accents."""
    return (base_hue + GOLDEN_ANGLE * steps) % 360


def golden_lightness(bg_l: float) -> float:
    """Compute foreground lightness using golden-ratio formula.
    Ensures comfortable reading contrast regardless of hue."""
    if bg_l > 0.5:
        return bg_l * (1 - 1 / PHI)  # ≈ bg_l * 0.382
    else:
        return bg_l + (1 - bg_l) * (1 / PHI)


# ═══════════════════════════════════════════════
#  ThemeManager
# ═══════════════════════════════════════════════

class ThemeManager:
    """Generates complete QSS stylesheets from OKLCH parameters."""

    # Base parameters — adjustable at runtime
    HUE = 220
    CHROMA = 0.12

    # Dark-mode lightness values (perceptual, 0-1)
    DARK = {
        'bg_main': 0.10,       # #1a1a2e equivalent
        'bg_card': 0.16,       # card / group box background
        'bg_widget': 0.14,     # input / list background
        'bg_sidebar': 0.12,    # sidebar
        'bg_surface': 0.20,    # elevated surface
        'text_primary': 1.0,   # will be overridden by contrast calc
        'text_secondary': 0.60,
        'text_muted': 0.40,
        'accent': 0.65,
        'border': 0.25,
    }

    LIGHT = {
        'bg_main': 0.96,
        'bg_card': 0.98,
        'bg_widget': 1.0,
        'bg_sidebar': 0.93,
        'bg_surface': 0.90,
        'text_primary': 0.0,
        'text_secondary': 0.35,
        'text_muted': 0.55,
        'accent': 0.50,
        'border': 0.85,
    }

    def __init__(self, mode: str = 'dark', hue: float = 220, chroma: float = 0.12):
        self.mode = mode
        self.HUE = hue
        self.CHROMA = chroma

    # ── palette ──────────────────────────────────────────────

    def palette(self) -> dict[str, str]:
        """Return a dict of hex colors for the current mode."""
        base = self.DARK if self.mode == 'dark' else self.LIGHT
        p = {}

        for name, l_val in base.items():
            if name.startswith('text_') or name == 'accent' or name == 'border':
                c_val = self.CHROMA * 0.8 if name in ('text_muted', 'border') else self.CHROMA
            else:
                c_val = self.CHROMA * 0.5 if 'bg' in name else self.CHROMA
            p[name] = oklch_to_hex(l_val, c_val, self.HUE)

        # Accent uses higher chroma and golden-shifted hue for harmony
        accent_l = base['accent']
        accent_h = golden_shift_hue(self.HUE, 2)
        p['accent'] = oklch_to_hex(accent_l, self.CHROMA * 1.2, accent_h)

        # Compute best text color against bg_main
        bg_rgb = oklch_to_rgb(base['bg_main'], self.CHROMA * 0.3, self.HUE)
        p['text_primary'] = best_text_color(bg_rgb)

        # Secondary text: golden-ratio lightness from bg_main
        sec_l = golden_lightness(base['bg_main'])
        sec_rgb = oklch_to_rgb(sec_l, self.CHROMA * 0.3, self.HUE)
        p['text_secondary'] = rgb_to_hex(*sec_rgb)

        # Muted / tertiary
        muted_l = base['bg_main'] + (1 - 2 * base['bg_main']) * 0.3 if base['bg_main'] < 0.5 else base['bg_main'] * 0.7
        muted_rgb = oklch_to_rgb(muted_l, self.CHROMA * 0.15, self.HUE)
        p['text_muted'] = rgb_to_hex(*muted_rgb)

        # Success / danger / warning — fixed hues for universal recognition
        p['success'] = oklch_to_hex(0.55, 0.18, 142)   # green
        p['danger'] = oklch_to_hex(0.50, 0.20, 25)     # red
        p['warning'] = oklch_to_hex(0.60, 0.18, 85)    # yellow/amber

        # Border
        border_l = base['border']
        p['border'] = oklch_to_hex(border_l, self.CHROMA * 0.5, self.HUE)

        return p

    # ── QSS generation ───────────────────────────────────────

    def generate_qss(self) -> str:
        p = self.palette()
        bg = p['bg_main']
        bg_card = p['bg_card']
        bg_widget = p['bg_widget']
        bg_sidebar = p['bg_sidebar']
        bg_surface = p['bg_surface']
        tx = p['text_primary']
        tx2 = p['text_secondary']
        tx3 = p['text_muted']
        ac = p['accent']
        bd = p['border']
        sc = p['success']
        dg = p['danger']
        wn = p['warning']

        # Transparency variants for hover/pressed states
        hover_bg = f'rgba({_hex_to_rgba(ac, 0.15)})'
        selected_bg = f'rgba({_hex_to_rgba(ac, 0.3)})'

        return f'''
/* === Auto-generated OKLCH theme ({self.mode}) === */

QMainWindow {{
    background-color: {bg};
}}

QWidget {{
    color: {tx};
    font-size: 13px;
}}

QLabel {{
    color: {tx2};
    background: transparent;
}}

/* ── Group Box / Cards ── */
QGroupBox {{
    color: {tx};
    border: 1px solid {bd};
    border-radius: 8px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-size: 13px;
    font-weight: bold;
    background-color: {bg_card};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {ac};
}}

/* ── Inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {bg_widget};
    border: 1px solid {bd};
    border-radius: 4px;
    padding: 6px 10px;
    color: {tx};
    selection-background-color: {ac};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ac};
}}
QComboBox {{
    background-color: {bg_widget};
    border: 1px solid {bd};
    border-radius: 4px;
    padding: 6px 10px;
    color: {tx};
    min-width: 120px;
}}
QComboBox:hover {{
    border-color: {ac};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {bd};
}}
QComboBox QAbstractItemView {{
    background-color: {bg_widget};
    border: 1px solid {bd};
    selection-background-color: {ac};
    color: {tx};
}}

/* ── Scroll Area ── */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {tx3};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {tx2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ── Tab Widget ── */
QTabWidget::pane {{
    border: none;
    background-color: {bg};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {tx3};
    padding: 10px 24px;
    font-size: 13px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {tx};
    border-bottom: 2px solid {ac};
}}
QTabBar::tab:hover {{
    color: {tx2};
    background-color: {hover_bg};
}}

/* ── Lists / Trees / Tables ── */
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {bg_widget};
    border: 1px solid {bd};
    border-radius: 4px;
    color: {tx2};
    outline: none;
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: 6px 12px;
    border-bottom: 1px solid {bd};
}}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background-color: {ac};
    color: #ffffff;
}}
QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {hover_bg};
}}
QHeaderView::section {{
    background-color: {bg_surface};
    color: {tx3};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {bd};
    font-weight: bold;
    font-size: 12px;
}}

/* ── Push Buttons ── */
QPushButton {{
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: bold;
    border: none;
    color: {tx};
    background-color: {bg_surface};
}}
QPushButton:hover {{
    background-color: {hover_bg};
}}
QPushButton:pressed {{
    background-color: {selected_bg};
}}
QPushButton:disabled {{
    color: {tx3};
    background-color: {bg_widget};
}}
QPushButton#btn_start {{
    background-color: {sc};
    color: #ffffff;
}}
QPushButton#btn_start:hover {{
    opacity: 0.9;
}}
QPushButton#btn_stop {{
    background-color: {dg};
    color: #ffffff;
}}
QPushButton#btn_pause {{
    background-color: {wn};
    color: #1a1a1a;
}}
QPushButton#btn_save {{
    background-color: {ac};
    color: #ffffff;
}}

/* ── Sidebar ── */
#sidebar {{
    background-color: {bg_sidebar};
    border-right: 1px solid {bd};
}}

/* ── Bottom bar ── */
#bottomBar {{
    background-color: {bg_surface};
    border-top: 1px solid {bd};
}}

/* ── Toolbar ── */
#toolbar {{
    background-color: {bg_surface};
    border-bottom: 1px solid {bd};
    padding: 4px 0;
}}

/* ── Log view ── */
#logView {{
    background-color: {bg_widget};
    color: {tx2};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    border: none;
    padding: 10px;
}}

/* ── Status bar ── */
#statusBar {{
    color: {tx3};
    font-size: 12px;
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {bg_surface};
    color: {tx};
    border: 1px solid {bd};
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}}
'''


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert #rrggbb to rgba(r,g,b,a) string."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'{r},{g},{b},{alpha}'


# ═══════════════════════════════════════════════
#  Global instance
# ═══════════════════════════════════════════════

_theme_manager: ThemeManager | None = None


def get_theme() -> ThemeManager:
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager('dark')
    return _theme_manager


def set_theme_mode(mode: str):
    """Switch theme mode ('dark' | 'light') and re-apply."""
    tm = get_theme()
    tm.mode = mode
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        app.setStyleSheet(tm.generate_qss())
