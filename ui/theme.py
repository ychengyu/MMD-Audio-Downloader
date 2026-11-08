"""
Fluent Design Theme and Color Palette System for MMD Audio Downloader.
Supports Dark, Light, and Windows System theme detection,
along with customizable accent colors (Teal, Blue, Purple, Pink, Orange, Custom HEX).
"""

import sys
from typing import Dict, Tuple
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from core.config import ConfigManager


PRESET_ACCENTS: Dict[str, str] = {
    "青綠 (初音綠)": "#00D2B4",
    "經典藍": "#0078D4",
    "優雅紫": "#7C4DFF",
    "活力粉": "#FF4081",
    "暖陽橘": "#FF6D00",
}


def get_windows_system_theme() -> str:
    """Read Windows 10/11 system personalization registry for Dark/Light mode."""
    if sys.platform != "win32":
        return "dark"
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if val == 1 else "dark"
    except Exception:
        return "dark"


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert hex string (#RRGGBB) to (r, g, b) tuple."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        return (0, 210, 180)
    try:
        return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 210, 180)


def adjust_color(hex_str: str, factor: float) -> str:
    """Lighten (factor > 1.0) or darken (factor < 1.0) a hex color."""
    r, g, b = hex_to_rgb(hex_str)
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return f"#{r:02X}{g:02X}{b:02X}"


def get_contrast_text_color(hex_str: str) -> str:
    """Return #FFFFFF or #0E151B depending on background luminance."""
    r, g, b = hex_to_rgb(hex_str)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#0E151B" if luminance > 0.55 else "#FFFFFF"


class ThemeManager(QObject):
    """Centralized theme and accent color state manager with hot reload signals."""

    theme_changed = Signal(str, str)  # mode ("dark"/"light"), accent_hex

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self.config_mgr = ConfigManager()
        cfg = self.config_mgr.get()

        self._theme_mode = getattr(cfg, "theme_mode", "dark") or "dark"
        self._accent_color = getattr(cfg, "accent_color", "#00D2B4") or "#00D2B4"
        self._initialized = True

    @property
    def theme_mode(self) -> str:
        return self._theme_mode

    @property
    def accent_color(self) -> str:
        return self._accent_color

    def is_dark(self) -> bool:
        if self._theme_mode == "system":
            return get_windows_system_theme() == "dark"
        return self._theme_mode == "dark"

    def set_theme_mode(self, mode: str):
        if mode not in ("dark", "light", "system"):
            mode = "dark"
        self._theme_mode = mode

        # Persist
        cfg = self.config_mgr.get()
        cfg.theme_mode = mode
        cfg.theme = "dark" if self.is_dark() else "light"
        self.config_mgr.save(cfg)

        self.apply_theme()

    def set_accent_color(self, hex_color: str):
        # Validate hex color
        if not hex_color.startswith("#"):
            hex_color = f"#{hex_color}"
        if len(hex_color) != 7:
            return
        self._accent_color = hex_color.upper()

        # Persist
        cfg = self.config_mgr.get()
        cfg.accent_color = self._accent_color
        self.config_mgr.save(cfg)

        self.apply_theme()

    def apply_theme(self, target_widget: QWidget = None):
        """Re-render global application QSS and broadcast change."""
        qss = self.generate_stylesheet()
        dark = self.is_dark()
        r, g, b = hex_to_rgb(self._accent_color)
        accent_text = get_contrast_text_color(self._accent_color)

        app = QApplication.instance()
        if app:
            palette = QPalette()
            if dark:
                palette.setColor(QPalette.ColorRole.Window, QColor("#141519"))
                palette.setColor(QPalette.ColorRole.WindowText, QColor("#F5F7FA"))
                palette.setColor(QPalette.ColorRole.Base, QColor("#181920"))
                palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#20232B"))
                palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#20232B"))
                palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F5F7FA"))
                palette.setColor(QPalette.ColorRole.Text, QColor("#F5F7FA"))
                palette.setColor(QPalette.ColorRole.Button, QColor("#282C36"))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor("#F5F7FA"))
                palette.setColor(QPalette.ColorRole.Highlight, QColor(r, g, b))
                palette.setColor(QPalette.ColorRole.HighlightedText, QColor(accent_text))
            else:
                palette.setColor(QPalette.ColorRole.Window, QColor("#F5F6F9"))
                palette.setColor(QPalette.ColorRole.WindowText, QColor("#191B20"))
                palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
                palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F0F2F6"))
                palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
                palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#191B20"))
                palette.setColor(QPalette.ColorRole.Text, QColor("#191B20"))
                palette.setColor(QPalette.ColorRole.Button, QColor("#F0F2F6"))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor("#191B20"))
                palette.setColor(QPalette.ColorRole.Highlight, QColor(r, g, b))
                palette.setColor(QPalette.ColorRole.HighlightedText, QColor(accent_text))
            app.setPalette(palette)
            app.setStyleSheet(qss)
            for top_w in app.topLevelWidgets():
                top_w.setStyleSheet(qss)
        if target_widget and target_widget not in (app.topLevelWidgets() if app else []):
            target_widget.setStyleSheet(qss)

        effective_mode = "dark" if dark else "light"
        self.theme_changed.emit(effective_mode, self._accent_color)

    def generate_stylesheet(self) -> str:
        dark = self.is_dark()
        accent = self._accent_color
        r, g, b = hex_to_rgb(accent)

        accent_hover = adjust_color(accent, 1.12)
        accent_pressed = adjust_color(accent, 0.88)
        accent_text = get_contrast_text_color(accent)
        accent_title = accent if dark else adjust_color(accent, 0.65)
        accent_alpha_12 = f"rgba({r}, {g}, {b}, 0.12)"
        accent_alpha_20 = f"rgba({r}, {g}, {b}, 0.20)"
        accent_alpha_30 = f"rgba({r}, {g}, {b}, 0.30)"
        accent_alpha_40 = f"rgba({r}, {g}, {b}, 0.40)"

        if dark:
            bg_main = "#0F1014"
            bg_sidebar = "#14161C"
            bg_sidebar_hover = "#1E222B"
            bg_card = "#181B23"
            bg_card_alt = "#212530"
            bg_hover = "#272C39"
            bg_input = "#121419"
            text_primary = "#F2F3F5"
            text_secondary = "#8E95A5"
            text_muted = "#656D7E"
            border_color = "#262A35"
            border_light = "#1E212A"
            danger_color = "#FF5252"
            warning_color = "#FFB300"
            success_color = "#00E676"
        else:
            bg_main = "#F3F4F7"
            bg_sidebar = "#E8EAF0"
            bg_sidebar_hover = "#DDE0E8"
            bg_card = "#FFFFFF"
            bg_card_alt = "#F0F2F6"
            bg_hover = "#E1E4EC"
            bg_input = "#FFFFFF"
            text_primary = "#181A20"
            text_secondary = "#555D6E"
            text_muted = "#8E95A5"
            border_color = "#D2D6E2"
            border_light = "#E4E7F0"
            danger_color = "#E53935"
            warning_color = "#FB8C00"
            success_color = "#2E7D32"

        return f"""
        /* Global Reset - Base Theme: {'#141519' if dark else '#F5F6F9'} */
        QWidget {{
            font-family: "Microsoft JhengHei UI";
            font-size: 13px;
            color: {text_primary};
        }}

        QMainWindow, QDialog, #central_widget, QStackedWidget {{
            background-color: {bg_main};
            color: {text_primary};
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {bg_card};
            color: {text_primary};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 12px;
        }}

        /* Top Header Bar */
        #top_header {{
            background-color: {bg_main};
            border-bottom: 1px solid {border_color};
            min-height: 44px;
        }}

        /* Sidebar Container */
        #sidebar {{
            background-color: {bg_sidebar};
            border-right: 1px solid {border_color};
        }}

        /* Sidebar Navigation Buttons */
        QPushButton[class="nav_button"] {{
            text-align: left;
            padding: 8px 14px;
            font-weight: 500;
            font-size: 13px;
            color: {text_secondary};
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            min-height: 24px;
        }}
        QPushButton[class="nav_button"]:hover {{
            background-color: {bg_sidebar_hover};
            color: {text_primary};
        }}
        QPushButton[class="nav_button"]:checked {{
            background-color: {accent_alpha_20};
            color: {accent_title};
            font-weight: bold;
            border: 1px solid {accent};
        }}

        /* Hero Nav Button */
        QPushButton[class="nav_hero_button"] {{
            text-align: left;
            padding: 8px 12px;
            font-weight: 600;
            font-size: 13px;
            color: {accent_title};
            background-color: {accent_alpha_12};
            border: 1px solid {accent_alpha_40};
            border-radius: 7px;
            min-height: 20px;
        }}
        QPushButton[class="nav_hero_button"]:hover {{
            background-color: {accent_alpha_30};
        }}
        QPushButton[class="nav_hero_button"]:checked {{
            background-color: {accent};
            color: {accent_text};
            border: none;
        }}

        /* Scroll Area */
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollArea > QWidget#qt_scrollarea_viewport {{
            background-color: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {border_color};
            min-height: 24px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {accent};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}

        /* Card Containers */
        QFrame[class="card"] {{
            background-color: {bg_card};
            border: 1px solid {border_color};
            border-radius: 10px;
            padding: 12px 14px;
        }}

        QFrame[class="hero_card"] {{
            background: {bg_card};
            border: 1px solid {accent_alpha_40};
            border-radius: 10px;
            padding: 14px;
        }}

        /* Standard Buttons */
        QPushButton {{
            background-color: {bg_card_alt};
            color: {text_primary};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 500;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: {bg_hover};
            border-color: {accent};
        }}
        QPushButton:pressed {{
            background-color: {border_color};
        }}
        QPushButton:disabled {{
            background-color: {border_light};
            color: {text_muted};
            border-color: {border_light};
        }}

        /* Primary Accent Button */
        QPushButton[class="primary"] {{
            background-color: {accent};
            color: {accent_text};
            border: none;
            font-weight: bold;
            padding: 8px 18px;
            border-radius: 7px;
            min-height: 24px;
        }}
        QPushButton[class="primary"]:hover {{
            background-color: {accent_hover};
        }}
        QPushButton[class="primary"]:pressed {{
            background-color: {accent_pressed};
        }}

        /* Danger Button */
        QPushButton[class="danger"] {{
            background-color: transparent;
            color: {danger_color};
            border: 1px solid {danger_color};
            border-radius: 6px;
        }}
        QPushButton[class="danger"]:hover {{
            background-color: {danger_color};
            color: #FFFFFF;
        }}

        /* Inputs */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {bg_input};
            color: {text_primary};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 6px 10px;
            selection-background-color: {accent};
            selection-color: {accent_text};
            min-height: 20px;
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 1.5px solid {accent};
        }}

        /* ComboBox */
        QComboBox {{
            background-color: {bg_input};
            color: {text_primary};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 5px 12px;
            min-width: 90px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {accent};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {bg_card};
            color: {text_primary};
            border: 1px solid {border_color};
            border-radius: 6px;
            selection-background-color: {accent};
            selection-color: {accent_text};
            padding: 4px;
        }}

        /* SpinBox */
        QSpinBox, QDoubleSpinBox {{
            background-color: {bg_input};
            color: {text_primary};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 5px 10px;
            min-height: 20px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {accent};
        }}

        /* CheckBox */
        QCheckBox {{
            spacing: 8px;
            color: {text_primary};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1.5px solid {border_color};
            background-color: {bg_input};
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent};
            border-color: {accent};
        }}

        /* RadioButton */
        QRadioButton {{
            spacing: 8px;
            color: {text_primary};
        }}
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 8px;
            border: 1.5px solid {border_color};
            background-color: {bg_input};
        }}
        QRadioButton::indicator:checked {{
            background-color: {accent};
            border-color: {accent};
        }}

        /* ProgressBar */
        QProgressBar {{
            background-color: {bg_input};
            border: 1px solid {border_color};
            border-radius: 3px;
            text-align: center;
            height: 6px;
            color: transparent;
        }}
        QProgressBar::chunk {{
            background-color: {accent};
            border-radius: 2px;
        }}

        /* Sliders */
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background: {border_color};
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {accent};
            border: 2px solid {bg_card};
            width: 14px;
            margin-top: -5px;
            margin-bottom: -5px;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {accent_hover};
        }}

        /* TableWidget */
        QTableWidget {{
            background-color: {bg_card};
            border: 1px solid {border_color};
            border-radius: 8px;
            gridline-color: {border_light};
            selection-background-color: {bg_hover};
            selection-color: {text_primary};
        }}
        QHeaderView::section {{
            background-color: {bg_card_alt};
            color: {text_secondary};
            font-weight: 600;
            padding: 6px 10px;
            border: none;
            border-bottom: 1px solid {border_color};
        }}

        /* GroupBox */
        QGroupBox {{
            font-weight: bold;
            font-size: 13px;
            border: 1px solid {border_color};
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 12px;
            background-color: {bg_card};
            color: {text_primary};
        }}
            margin-top: 14px;
            padding-top: 16px;
            background-color: {bg_card};
            color: {text_primary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 0 6px;
            color: {accent_title};
        }}

        /* Thumbnail Container */
        #thumbnail_frame {{
            background-color: {bg_card_alt};
            border: 1px solid {border_color};
            border-radius: 10px;
        }}

        /* Badges */
        QLabel[class="badge_success"] {{
            background-color: rgba(0, 230, 118, 0.15);
            color: {success_color};
            border: 1px solid {success_color};
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: bold;
            font-size: 11px;
        }}
        QLabel[class="badge_warning"] {{
            background-color: rgba(255, 179, 0, 0.15);
            color: {warning_color};
            border: 1px solid {warning_color};
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: bold;
            font-size: 11px;
        }}
        """
