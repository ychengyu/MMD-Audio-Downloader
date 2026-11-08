"""
Hero Banner Component for MMD Audio Downloader.
Displays a top banner featuring Fluent Design 2 aesthetic:
a cyan accent bar, prominent title, detailed description, glowing abstract wave graphics,
and an iconic badge representing the active module.
"""

from typing import List, Optional, Union
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from ui.theme import ThemeManager


class HeroBannerWidget(QFrame):
    """
    Sleek top banner card with title, description, and an abstract glowing wave illustration.
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

        self.setFixedHeight(94)
        self.setObjectName("hero_banner")
        self.setProperty("class", "card")

        self._setup_ui()
        self.theme_mgr.theme_changed.connect(lambda *_: self.update())

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 12, 22, 12)
        main_layout.setSpacing(14)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Left: Vertical Cyan Accent Line + Texts
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Accent Bar
        self.accent_bar = QFrame()
        self.accent_bar.setFixedSize(4, 38)
        self.accent_bar.setStyleSheet("background-color: #00D2B4; border-radius: 2px;")
        left_layout.addWidget(self.accent_bar)

        # Text Column
        text_v = QVBoxLayout()
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(3)
        text_v.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.text_col = text_v

        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet("font-size: 19px; font-weight: bold; color: #FFFFFF; background: transparent;")
        text_v.addWidget(self.title_label)

        for line in self.desc_text:
            lbl = QLabel(line)
            lbl.setStyleSheet("font-size: 12px; color: #A3AAB8; background: transparent;")
            lbl.setWordWrap(False)
            text_v.addWidget(lbl)

        left_layout.addLayout(text_v)
        main_layout.addLayout(left_layout, 1)

        # Optional middle/right custom widget (e.g. Unified target format combobox in ConverterView)
        if self.right_widget:
            main_layout.addWidget(self.right_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Right Spacer for Wave Illustration and Badge
        self.badge_container = QWidget()
        self.badge_container.setFixedSize(90, 70)
        main_layout.addWidget(self.badge_container, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        accent = QColor(self.theme_mgr.accent_color)
        is_dark = self.theme_mgr.is_dark()

        # 1. Base Card Background
        bg_color = QColor("#141822") if is_dark else QColor("#FFFFFF")
        border_col = QColor("#242936") if is_dark else QColor("#D8DCE6")

        painter.setPen(QPen(border_col, 1))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)

        # 2. Glowing Abstract Waves on the right
        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)
        painter.setClipPath(clip_path)

        # Wave 1 (Upper smooth curve)
        wave1 = QPainterPath()
        wave1.moveTo(w - 380, h)
        wave1.cubicTo(w - 280, h * 0.2, w - 160, h * 0.8, w, h * 0.25)
        wave1.lineTo(w, h)
        wave1.closeSubpath()

        grad1 = QLinearGradient(w - 380, 0, w, h)
        col1_start = QColor(accent.red(), accent.green(), accent.blue(), 18)
        col1_end = QColor(accent.red(), accent.green(), accent.blue(), 60)
        grad1.setColorAt(0.0, col1_start)
        grad1.setColorAt(1.0, col1_end)
        painter.fillPath(wave1, QBrush(grad1))

        # Wave 1 Stroke
        pen_wave = QPen(QColor(accent.red(), accent.green(), accent.blue(), 85), 1.2)
        wave1_stroke = QPainterPath()
        wave1_stroke.moveTo(w - 380, h)
        wave1_stroke.cubicTo(w - 280, h * 0.2, w - 160, h * 0.8, w, h * 0.25)
        painter.strokePath(wave1_stroke, pen_wave)

        # Wave 2 (Lower smooth crossing curve)
        wave2 = QPainterPath()
        wave2.moveTo(w - 320, 0)
        wave2.cubicTo(w - 220, h * 0.8, w - 120, h * 0.2, w, h * 0.7)
        painter.strokePath(wave2, QPen(QColor(accent.red(), accent.green(), accent.blue(), 55), 1.0))

        # 3. Badge Illustration Container
        badge_x = w - 84
        badge_y = 15
        badge_w = 60
        badge_h = 60

        # Badge Rounded Box
        badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 140), 1.2))
        badge_grad = QLinearGradient(badge_x, badge_y, badge_x + badge_w, badge_y + badge_h)
        badge_grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 35))
        badge_grad.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 15))
        painter.setBrush(QBrush(badge_grad))
        painter.drawRoundedRect(badge_rect, 10, 10)

        # Badge Icon Graphic
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 255)))
        painter.setFont(QFont("Microsoft JhengHei UI", 18, QFont.Weight.Bold))

        icon_char = "♫"
        sub_text = ""
        if self.badge_type == "wav":
            icon_char = "♫"
            sub_text = "WAV"
        elif self.badge_type == "download":
            icon_char = "▶"
            sub_text = "↓"
        elif self.badge_type == "converter":
            icon_char = "♫"
            sub_text = "⇄"
        elif self.badge_type == "tasks":
            icon_char = "📋"
            sub_text = "✓"
        elif self.badge_type == "settings":
            icon_char = "⚙"
            sub_text = ""

        # Draw main icon
        painter.drawText(
            QRectF(badge_x, badge_y + 4, badge_w, 32),
            Qt.AlignmentFlag.AlignCenter,
            icon_char,
        )

        # Draw small sub-badge pill if present
        if sub_text:
            sub_w = 34
            sub_h = 14
            sub_x = badge_x + (badge_w - sub_w) / 2
            sub_y = badge_y + 38
            pill_rect = QRectF(sub_x, sub_y, sub_w, sub_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            painter.drawRoundedRect(pill_rect, 3, 3)

            painter.setPen(QPen(QColor("#081116")))
            painter.setFont(QFont("Segoe UI Variable", 8, QFont.Weight.Bold))
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, sub_text)

        painter.restore()
