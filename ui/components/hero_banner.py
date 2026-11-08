"""
Page Header Component for MMD Audio Downloader.
Displays a clean, modern Windows 11 Fluent Design header matching the official mockups:
prominent page title with icon (22px bold), crisp subtitle (13px secondary text),
and optional right-aligned widget (e.g., target format combobox).
"""

from typing import List, Optional, Union
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from ui.theme import ThemeManager


class HeroBannerWidget(QWidget):
    """
    Clean page header with title, subtitle, and optional right control widget.
    Matches 01_mmd_wav_zone.png through 05_settings_view.png 1:1.
    """

    def __init__(
        self,
        title: str,
        desc: Union[str, List[str]],
        badge_type: str = "wav",
        right_widget: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.title_text = title
        self.desc_text = desc if isinstance(desc, list) else [desc]
        self.badge_type = badge_type
        self.right_widget = right_widget
        self.theme_mgr = ThemeManager()

        self.setObjectName("page_header")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._setup_ui()
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 8, 4)
        main_layout.setSpacing(16)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Left Column: Title + Subtitle
        text_v = QVBoxLayout()
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(3)
        text_v.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.text_col = text_v

        # Title Label (22px bold)
        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #FFFFFF; background: transparent; padding: 0px;"
        )
        text_v.addWidget(self.title_label)

        # Subtitle Labels (13px)
        self.desc_labels = []
        for line in self.desc_text:
            lbl = QLabel(line)
            lbl.setStyleSheet(
                "font-size: 13px; color: #A3AAB8; background: transparent; padding: 0px;"
            )
            lbl.setWordWrap(True)
            text_v.addWidget(lbl)
            self.desc_labels.append(lbl)

        main_layout.addLayout(text_v, 1)

        # Optional right custom widget (e.g., target format combobox in ConverterView)
        if self.right_widget:
            main_layout.addWidget(self.right_widget, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

    def set_title(self, text: str):
        self.title_text = text
        self.title_label.setText(text)

    def set_desc(self, desc: Union[str, List[str]]):
        self.desc_text = desc if isinstance(desc, list) else [desc]
        for lbl in self.desc_labels:
            self.text_col.removeWidget(lbl)
            lbl.deleteLater()
        self.desc_labels.clear()
        for line in self.desc_text:
            lbl = QLabel(line)
            is_dark = self.theme_mgr.is_dark()
            color = "#A3AAB8" if is_dark else "#5A6272"
            lbl.setStyleSheet(
                f"font-size: 13px; color: {color}; background: transparent; padding: 0px;"
            )
            lbl.setWordWrap(True)
            self.text_col.addWidget(lbl)
            self.desc_labels.append(lbl)

    def _on_theme_changed(self, mode: str, accent: str):
        is_dark = self.theme_mgr.is_dark()
        title_color = "#FFFFFF" if is_dark else "#111318"
        desc_color = "#A3AAB8" if is_dark else "#5A6272"

        self.title_label.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {title_color}; background: transparent; padding: 0px;"
        )
        for lbl in self.desc_labels:
            lbl.setStyleSheet(
                f"font-size: 13px; color: {desc_color}; background: transparent; padding: 0px;"
            )


# Alias for backwards compatibility
PageHeaderWidget = HeroBannerWidget
