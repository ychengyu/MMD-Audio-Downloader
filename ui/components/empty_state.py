"""
Modern Windows 11 Fluent Empty State Widget for MMD Audio Downloader.
Displays beautiful guidance when task lists or tables have no items.
"""

from typing import Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import ThemeManager


class EmptyStateWidget(QFrame):
    """Clean card showing an empty state placeholder with optional action button."""

    def __init__(
        self,
        icon_text: str = "📋",
        title: str = "目前尚無項目",
        description: str = "",
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._setup_ui(icon_text, title, description, action_text, action_callback)

    def _setup_ui(
        self,
        icon_text: str,
        title: str,
        description: str,
        action_text: Optional[str],
        action_callback: Optional[Callable[[], None]]
    ):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon
        self.icon_lbl = QLabel(icon_text)
        self.icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_lbl)

        # Title
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_lbl)

        # Description
        if description:
            self.desc_lbl = QLabel(description)
            self.desc_lbl.setStyleSheet("font-size: 12px; color: #A3AAB8; line-height: 1.4; background: transparent;")
            self.desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.desc_lbl.setWordWrap(True)
            layout.addWidget(self.desc_lbl)

        # Optional Action Button
        if action_text and action_callback:
            layout.addSpacing(6)
            self.action_btn = QPushButton(action_text)
            self.action_btn.setProperty("class", "primary")
            self.action_btn.setMinimumHeight(36)
            self.action_btn.clicked.connect(action_callback)
            layout.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignCenter)
