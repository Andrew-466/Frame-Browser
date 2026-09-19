"""Theme colors, stylesheet, Qt palette, and global applier."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from .icons import check_png_path, close_png_path

THEMES = {
    "dark": {
        "bg": "#16181d",
        "bg_light": "#22262e",
        "bg_lighter": "#2c313a",
        "toolbar": "#1b1e25",
        "toolbar_glow": "#1e2531",
        "tab_active": "#2c313a",
        "statusbar": "#1b1e25",

        "accent": "#7ea6ff",
        "accent_hover": "#96b8ff",
        "accent_soft": "rgba(126, 166, 255, 38)",
        "accent_subtle": "rgba(126, 166, 255, 20)",
        "accent_glow": "rgba(126, 166, 255, 90)",

        "text": "#e8ecf2",
        "text_dim": "#c5cdd8",
        "border": "#333942",
        "border_light": "#3f4650",
        "muted": "#8c95a3",

        "check_fg": "#16181d",
    },
    "light": {
        "bg": "#eef2f7",
        "bg_light": "#ffffff",
        "bg_lighter": "#f5f8fc",
        "toolbar": "#e3ebf5",
        "toolbar_glow": "#dbe6f5",
        "tab_active": "#ffffff",
        "statusbar": "#e3ebf5",

        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_soft": "rgba(37, 99, 235, 26)",
        "accent_subtle": "rgba(37, 99, 235, 15)",
        "accent_glow": "rgba(37, 99, 235, 70)",

        "text": "#1a1f2e",
        "text_dim": "#3b4252",
        "border": "#d0d8e5",
        "border_light": "#e0e6f0",
        "muted": "#64748b",

        "check_fg": "#ffffff",
    },
}


def build_stylesheet(theme: str = "dark") -> str:
    c = THEMES.get(theme, THEMES["dark"])
    check_path = check_png_path(c.get("check_fg", "#ffffff"), 16)
    check_rule = (
        f'image: url("{check_path}");'
        if check_path
        else ""
    )

    return f"""
    /* ═══════════════════════════════════════════════════════════
       Base
       ═══════════════════════════════════════════════════════════ */
    QMainWindow, QDialog {{
        background-color: {c['bg']};
    }}
    QWidget {{
        color: {c['text']};
    }}
    QLabel {{
        background: transparent;
        color: {c['text']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Custom Title Bar
       ═══════════════════════════════════════════════════════════ */
    QWidget#CustomTitleBar {{
        background-color: {c['toolbar']};
        border-bottom: 1px solid {c['border']};
    }}
    QLabel#CustomTitleBarTitle {{
        color: {c['text']};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.2px;
        background: transparent;
    }}
    QLabel#CustomTitleBarIcon {{
        background: transparent;
    }}
    QToolButton#CustomTitleBarButton {{
        background: transparent;
        border: none;
        border-radius: 4px;
        color: {c['muted']};
        font-size: 14px;
        padding: 0;
    }}
    QToolButton#CustomTitleBarButton:hover {{
        background-color: {c['accent_subtle']};
        color: {c['accent']};
    }}
    QToolButton#CustomTitleBarButton:pressed {{
        background-color: {c['accent_soft']};
    }}
    QToolButton#CustomTitleBarClose:hover {{
        background-color: #e81123;
        color: #ffffff;
    }}
    QToolButton#CustomTitleBarClose:pressed {{
        background-color: #c50f1f;
        color: #ffffff;
    }}

    /* ═══════════════════════════════════════════════════════════
       Checkbox & Radio
       ═══════════════════════════════════════════════════════════ */
    QCheckBox {{
        spacing: 8px;
        color: {c['text']};
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c['border_light']};
        border-radius: 4px;
        background-color: {c['bg_light']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c['accent']};
        background-color: {c['accent_subtle']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
        {check_rule}
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: {c['accent_hover']};
        border-color: {c['accent_hover']};
    }}
    QCheckBox::indicator:disabled {{
        background-color: {c['bg']};
        border-color: {c['border']};
    }}
    QCheckBox::indicator:checked:disabled {{
        background-color: {c['muted']};
        border-color: {c['muted']};
    }}

    QRadioButton {{
        spacing: 8px;
        color: {c['text']};
        background: transparent;
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c['border_light']};
        border-radius: 8px;
        background-color: {c['bg_light']};
    }}
    QRadioButton::indicator:hover {{
        border-color: {c['accent']};
    }}
    QRadioButton::indicator:checked {{
        background-color: {c['accent']};
        border: 4px solid {c['bg_light']};
        outline: 1px solid {c['accent']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Group Box
       ═══════════════════════════════════════════════════════════ */
    QGroupBox {{
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        margin-top: 14px;
        padding: 12px 10px 10px 10px;
        font-weight: 600;
        background-color: {c['bg_light']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        color: {c['accent']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Toolbar
       ═══════════════════════════════════════════════════════════ */
    QToolBar {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['toolbar_glow']}, stop:1 {c['toolbar']});
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: 6px 8px;
        spacing: 4px;
    }}
    QToolBar QToolButton {{
        border-radius: 8px;
        padding: 6px;
        color: {c['text']};
    }}
    QToolBar QToolButton:hover {{
        background-color: {c['accent_subtle']};
    }}
    QToolBar QToolButton:pressed {{
        background-color: {c['accent_soft']};
    }}
    QToolButton::menu-indicator {{ image: none; }}

    /* ═══════════════════════════════════════════════════════════
       Line Edit / Plain Text Edit
       ═══════════════════════════════════════════════════════════ */
    QLineEdit {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 14px;
        padding: 6px 14px;
        font-size: 13px;
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QLineEdit:hover {{
        border-color: {c['border_light']};
    }}
    QLineEdit:focus {{
        border: 1px solid {c['accent']};
        background-color: {c['accent_subtle']};
    }}

    QPlainTextEdit {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 10px;
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size: 12px;
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QPlainTextEdit:focus {{
        border: 2px solid {c['accent']};
        background-color: {c['accent_subtle']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Tabs
       ═══════════════════════════════════════════════════════════ */
    QTabWidget::pane {{
        border: none;
        background: {c['bg']};
    }}
    QTabBar {{
        background: {c['bg']};
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {c['muted']};
        padding: 5px 8px;
        margin: 3px 2px 0 0;
        font-size: 12px;
        min-width: 144px;
        max-width: 144px;
        border: 1px solid transparent;
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
    }}
    QTabBar::tab:hover:!selected {{
        background: {c['bg_light']};
        color: {c['text']};
        border-top: 2px solid {c['accent_subtle']};
    }}
    QTabBar::tab:selected {{
        background: {c['tab_active']};
        color: {c['accent']};
        border: 1px solid {c['border']};
        border-top: 2px solid {c['accent']};
        border-bottom: none;
    }}
    QTabBar QToolButton#TabCloseButton {{
        background: transparent;
        border: none;
        border-radius: 6px;
        font-size: 12px;
        color: {c['muted']};
        padding: 0;
        margin: 0 10px 0 6px;
        min-width: 18px;
        min-height: 18px;
    }}
    QTabBar QToolButton#TabCloseButton:hover {{
        background: rgba(255, 80, 80, 0.22);
        color: {c['text']};
    }}
    QTabBar QToolButton#TabCloseButton:pressed {{
        background: rgba(255, 80, 80, 0.38);
    }}

    QToolButton#NewTabButton {{
        background: transparent;
        border: none;
        border-radius: 6px;
        font-size: 18px;
        font-weight: 400;
        color: {c['text']};
        padding: 0;
    }}
    QToolButton#NewTabButton:hover {{
        background-color: {c['accent_subtle']};
        color: {c['accent']};
    }}
    QToolButton#NewTabButton:pressed {{
        background-color: {c['accent_soft']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Status bar
       ═══════════════════════════════════════════════════════════ */
    QStatusBar {{
        background-color: {c['statusbar']};
        color: {c['muted']};
        border: none;
        font-size: 11px;
    }}
    QStatusBar::item {{ border: none; }}

    /* ═══════════════════════════════════════════════════════════
       Progress bar
       ═══════════════════════════════════════════════════════════ */
    QProgressBar {{
        background-color: {c['bg_light']};
        border: none;
        border-radius: 4px;
    }}
    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: 4px;
    }}

    /* ═══════════════════════════════════════════════════════════
       Buttons
       ═══════════════════════════════════════════════════════════ */
    QPushButton {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        border: 1px solid {c['accent']};
        background-color: {c['accent_soft']};
        color: {c['accent']};
    }}
    QPushButton:pressed {{
        background-color: {c['accent_glow']};
    }}
    QPushButton:focus {{
        border: 2px solid {c['accent']};
    }}
    QPushButton:disabled {{
        color: {c['muted']};
        background-color: {c['bg']};
        border-color: {c['border']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Lists
       ═══════════════════════════════════════════════════════════ */
    QListWidget {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 6px;
        color: {c['text']};
    }}
    QListWidget::item:hover {{
        background-color: {c['accent_subtle']};
    }}
    QListWidget::item:selected {{
        background-color: {c['accent_soft']};
        color: {c['accent']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Menus
       ═══════════════════════════════════════════════════════════ */
    QMenu {{
        background-color: {c['bg_light']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 26px 7px 14px;
        border-radius: 6px;
        color: {c['text']};
    }}
    QMenu::item:selected {{
        background-color: {c['accent_soft']};
        color: {c['accent']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c['border']};
        margin: 5px 8px;
    }}

    /* ═══════════════════════════════════════════════════════════
       Combo & Spin
       ═══════════════════════════════════════════════════════════ */
    QComboBox {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 10px;
        min-width: 160px;
    }}
    QComboBox:hover {{
        border-color: {c['border_light']};
    }}
    QComboBox:focus {{
        border: 2px solid {c['accent']};
        background-color: {c['accent_subtle']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent_soft']};
        selection-color: {c['accent']};
        outline: none;
    }}

    QSpinBox {{
        background-color: {c['bg_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 10px;
        min-width: 100px;
    }}
    QSpinBox:focus {{
        border: 2px solid {c['accent']};
        background-color: {c['accent_subtle']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Scroll area
       ═══════════════════════════════════════════════════════════ */
    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QFrame#BookmarkBar {{
        background-color: {c['toolbar']};
        border: none;
        border-bottom: 1px solid {c['accent_subtle']};
    }}

    /* ═══════════════════════════════════════════════════════════
       Dialog buttons
       ═══════════════════════════════════════════════════════════ */
    QDialogButtonBox QPushButton {{
        min-width: 80px;
    }}

    /* ═══════════════════════════════════════════════════════════
       Tooltips
       ═══════════════════════════════════════════════════════════ */
    QToolTip {{
        background-color: {c['bg_lighter']};
        color: {c['text']};
        border: 1px solid {c['accent_subtle']};
        padding: 4px 8px;
        border-radius: 4px;
    }}

    /* ═══════════════════════════════════════════════════════════
       Scrollbar
       ═══════════════════════════════════════════════════════════ */
    QScrollBar:vertical {{
        background: {c['bg']};
        width: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        min-height: 24px;
        border-radius: 5px;
        margin: 2px 1px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        background: transparent;
        border: none;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: {c['bg']};
        height: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        min-width: 24px;
        border-radius: 5px;
        margin: 1px 2px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
        background: transparent;
        border: none;
    }}
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
    """


def build_palette(theme: str = "dark") -> QPalette:
    """Qt palette fallback when stylesheet doesn't apply to some widget."""
    c = THEMES.get(theme, THEMES["dark"])
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(c["bg_light"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(c["bg"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(c["bg_light"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(c["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["muted"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["bg_lighter"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
    return pal


def apply_theme(theme_name: str) -> None:
    """Apply theme to the whole application (all top-level windows)."""
    app = QApplication.instance()
    if app is None:
        return

    app.setStyleSheet(build_stylesheet(theme_name))
    app.setPalette(build_palette(theme_name))

    style = app.style()
    if style is not None:
        for widget in app.allWidgets():
            try:
                style.unpolish(widget)
                style.polish(widget)
                widget.update()
            except RuntimeError:
                continue