"""
Card-based Format Selector Component for MMD Audio Downloader.
Implements modern Windows 11 Fluent card selection for WAV, MP3, MP4, FLAC, M4A
with clear visual hierarchy, indicators, hover states, and accent synchronization.
"""

from typing import Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.theme import ThemeManager, adjust_color, get_contrast_text_color, hex_to_rgb


FORMAT_DEFINITIONS = [
    {
        "key": "WAV",
        "icon": "|||",
        "title": "WAV",
        "tag": "MMD 專用音訊",
        "meta": "PCM 16-bit · 44.1 kHz",
        "is_video": False,
        "is_mmd": True
    },
    {
        "key": "MP3",
        "icon": "♫",
        "title": "MP3",
        "tag": "一般音樂",
        "meta": "最高 320 kbps",
        "is_video": False,
        "is_mmd": False
    },
    {
        "key": "MP4",
        "icon": "🎬",
        "title": "MP4",
        "tag": "完整影片",
        "meta": "影像 + 音訊",
        "is_video": True,
        "is_mmd": False
    },
    {
        "key": "FLAC",
        "icon": "▤",
        "title": "FLAC",
        "tag": "無損音訊",
        "meta": "高音質，檔案更小",
        "is_video": False,
        "is_mmd": False
    },
    {
        "key": "M4A",
        "icon": "♫",
        "title": "M4A",
        "tag": "蘋果相容",
        "meta": "AAC 高音質 · 省容量",
        "is_video": False,
        "is_mmd": False
    },
]


class FormatCard(QFrame):
    """Individual clickable format card matching the user's design reference."""

    clicked = Signal(str)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info = info
        self.key = info["key"]
        self.is_selected = False
        self._is_hovered = False

        self.setFixedHeight(78)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self._setup_ui()
        ThemeManager().theme_changed.connect(lambda *_: self.update_style())

    def _setup_ui(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(10, 6, 24, 6)
        h_layout.setSpacing(8)

        # Left Icon
        self.icon_label = QLabel(self.info.get("icon", "♫"))
        self.icon_label.setFixedWidth(20)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 15px; background: transparent;")
        h_layout.addWidget(self.icon_label)

        # Text Column (Fixed height per label prevents font-metric clipping in PySide6)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(self.info["title"])
        self.title_label.setFixedHeight(22)
        self.tag_label = QLabel(self.info["tag"])
        self.tag_label.setFixedHeight(18)
        self.meta_label = QLabel(self.info["meta"])
        self.meta_label.setFixedHeight(16)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.tag_label)
        text_layout.addWidget(self.meta_label)
        h_layout.addLayout(text_layout, 1)

        self.update_style()

    def set_selected(self, selected: bool):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update_style()
            self.update()

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def update_style(self):
        try:
            if not hasattr(self, "icon_label") or not hasattr(self, "title_label"):
                return
            tm = ThemeManager()
            dark = tm.is_dark()
            accent = tm.accent_color

            if dark:
                text_pri = "#F2F3F5"
                text_sec = "#A3AAB8"
                if self.is_selected:
                    title_col = "#FFFFFF"
                    tag_col = "#FFFFFF"
                    meta_col = "#B2BAC6"
                    icon_col = accent
                else:
                    title_col = text_pri
                    tag_col = "#D2D7E0"
                    meta_col = text_sec
                    icon_col = "#8C95A6"
            else:
                text_pri = "#181A20"
                text_sec = "#5E6575"
                if self.is_selected:
                    title_col = adjust_color(accent, 0.65)
                    tag_col = "#0E151B"
                    meta_col = "#444B59"
                    icon_col = accent
                else:
                    title_col = text_pri
                    tag_col = "#383E4C"
                    meta_col = text_sec
                    icon_col = "#7E8594"

            self.icon_label.setStyleSheet(f"font-size: 15px; color: {icon_col}; background: transparent; padding: 0px;")
            self.title_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {title_col}; background: transparent; padding: 0px;")
            self.tag_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {tag_col}; background: transparent; padding: 0px;")
            self.meta_label.setStyleSheet(f"font-size: 10px; color: {meta_col}; background: transparent; padding: 0px;")
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        radius = 8

        tm = ThemeManager()
        dark = tm.is_dark()
        accent = tm.accent_color
        r, g, b = hex_to_rgb(accent)

        # Background and Border
        path = QPainterPath()
        path.addRoundedRect(1, 1, w - 2, h - 2, radius, radius)

        if dark:
            if self.is_selected:
                bg_color = QColor(
                    int(24 * 0.85 + r * 0.15),
                    int(28 * 0.85 + g * 0.15),
                    int(36 * 0.85 + b * 0.15)
                )
                border_pen = QPen(QColor(r, g, b), 1.6)
            elif self._is_hovered:
                bg_color = QColor(36, 42, 54)
                border_pen = QPen(QColor(80, 88, 104), 1.2)
            else:
                bg_color = QColor(27, 30, 37)
                border_pen = QPen(QColor(52, 57, 68), 1.0)
        else:
            if self.is_selected:
                bg_color = QColor(
                    int(255 * 0.90 + r * 0.10),
                    int(255 * 0.90 + g * 0.10),
                    int(255 * 0.90 + b * 0.10)
                )
                border_pen = QPen(QColor(r, g, b), 1.6)
            elif self._is_hovered:
                bg_color = QColor(245, 247, 252)
                border_pen = QPen(QColor(180, 186, 198), 1.2)
            else:
                bg_color = QColor(255, 255, 255)
                border_pen = QPen(QColor(216, 221, 232), 1.0)

        painter.fillPath(path, bg_color)
        painter.setPen(border_pen)
        painter.drawPath(path)

        # Draw Indicator Circle (Top-Right)
        circle_x = w - 17
        circle_y = 17
        circle_r = 7.5

        if self.is_selected:
            # Accent circle with inner checkmark
            painter.setBrush(QBrush(QColor(r, g, b)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(circle_x, circle_y), circle_r, circle_r)

            check_col = QColor(get_contrast_text_color(accent))
            painter.setPen(QPen(check_col, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(int(circle_x - 3.5), int(circle_y), int(circle_x - 1), int(circle_y + 2.5))
            painter.drawLine(int(circle_x - 1), int(circle_y + 2.5), int(circle_x + 3.5), int(circle_y - 2.5))
        else:
            ring_color = QColor(80, 88, 104) if dark else QColor(176, 182, 196)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring_color, 1.5))
            painter.drawEllipse(QPointF(circle_x, circle_y), circle_r, circle_r)

        painter.end()
        super().paintEvent(event)


class FormatCardSelector(QWidget):
    """Container grouping all 5 format cards in a single sleek horizontal row."""

    format_changed = Signal(str)  # emits format key ("WAV", "MP3", "MP4", etc.)

    def __init__(self, default_format: str = "WAV", parent=None):
        super().__init__(parent)
        self.selected_format = default_format
        self.cards: Dict[str, FormatCard] = {}

        self._setup_ui()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Section Header
        self.header_label = QLabel("輸出格式")
        self.header_label.setFixedHeight(24)
        self.header_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #F2F3F5; background: transparent; padding: 0px;")
        main_layout.addWidget(self.header_label)

        # 5 Cards in a Single Horizontal Row
        cards_layout = QHBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        for item in FORMAT_DEFINITIONS:
            card = FormatCard(item, self)
            card.clicked.connect(self._on_card_clicked)
            self.cards[item["key"]] = card
            cards_layout.addWidget(card, 1)

        main_layout.addLayout(cards_layout)
        self.set_format(self.selected_format)

    def _on_card_clicked(self, key: str):
        self.set_format(key)
        self.format_changed.emit(key)

    def set_format(self, key: str):
        key = key.upper()
        if key not in self.cards:
            key = "WAV"

        self.selected_format = key
        for k, card in self.cards.items():
            card.set_selected(k == key)
        self.format_changed.emit(key)

    def get_selected_format(self) -> str:
        return self.selected_format

    def is_selected_video(self) -> bool:
        return self.selected_format in ("MP4", "MKV")

    def _on_theme_changed(self, mode: str, accent: str):
        for card in self.cards.values():
            card.update_style()
