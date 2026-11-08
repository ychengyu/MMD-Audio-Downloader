"""
Card-based Format Selector Component for MMD Audio Downloader.
Implements modern Windows 11 Fluent card selection for WAV, MP3, MP4, FLAC, M4A
matching reference 02_download_view.png 1:1.
"""

from typing import Dict, List, Optional
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
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
        "icon": "·|·",
        "title": "WAV",
        "tag": "MMD 專用音訊",
        "meta": "PCM 16-bit · 44.1 kHz",
        "is_video": False,
        "is_mmd": True,
    },
    {
        "key": "MP3",
        "icon": "♫",
        "title": "MP3",
        "tag": "一般音樂",
        "meta": "最高 320 kbps",
        "is_video": False,
        "is_mmd": False,
    },
    {
        "key": "MP4",
        "icon": "🎞",
        "title": "MP4",
        "tag": "完整影片",
        "meta": "影音 + 音訊",
        "is_video": True,
        "is_mmd": False,
    },
    {
        "key": "FLAC",
        "icon": "◈",
        "title": "FLAC",
        "tag": "無損音訊",
        "meta": "高音質 · 檔案更小",
        "is_video": False,
        "is_mmd": False,
    },
    {
        "key": "M4A",
        "icon": "♫",
        "title": "M4A",
        "tag": "蘋果相容",
        "meta": "AAC 高音質 · 容量省",
        "is_video": False,
        "is_mmd": False,
    },
    {
        "key": "MKV",
        "icon": "🎬",
        "title": "MKV",
        "tag": "多軌影片",
        "meta": "高畫質，支援多聲軌",
        "is_video": True,
        "is_mmd": False,
    },
]


class FormatCard(QFrame):
    """Individual clickable format card matching 02_download_view.png."""

    clicked = Signal(str)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info = info
        self.key = info["key"]
        self.is_selected = False
        self._is_hovered = False

        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

        self._setup_ui()
        ThemeManager().theme_changed.connect(lambda *_: self.update_style())

    def _setup_ui(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(12, 8, 28, 8)
        h_layout.setSpacing(8)

        # Left Icon
        self.icon_label = QLabel(self.info.get("icon", "♫"))
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 16px; background: transparent;")
        h_layout.addWidget(self.icon_label)

        # Text Column
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(self.info["title"])
        self.title_label.setFixedHeight(20)
        self.tag_label = QLabel(self.info["tag"])
        self.tag_label.setFixedHeight(16)
        self.meta_label = QLabel(self.info["meta"])
        self.meta_label.setFixedHeight(14)

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
                if self.is_selected:
                    title_col = "#FFFFFF"
                    tag_col = "#E8EDF4"
                    meta_col = "#A3AAB8"
                    icon_col = accent
                else:
                    title_col = "#F2F3F5"
                    tag_col = "#C2C8D4"
                    meta_col = "#828B9C"
                    icon_col = "#8E95A5"
            else:
                if self.is_selected:
                    title_col = "#061814"
                    tag_col = "#0D2620"
                    meta_col = "#38524B"
                    icon_col = adjust_color(accent, 0.75)
                else:
                    title_col = "#181A20"
                    tag_col = "#383E4C"
                    meta_col = "#656D7E"
                    icon_col = "#7E8594"

            self.icon_label.setStyleSheet(f"font-size: 16px; color: {icon_col}; background: transparent; padding: 0px;")
            self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {title_col}; background: transparent; padding: 0px;")
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
                # Dark teal tint with bright accent border
                bg_color = QColor(16, 36, 36)
                border_pen = QPen(QColor(r, g, b), 1.8)
            elif self._is_hovered:
                bg_color = QColor(32, 38, 48)
                border_pen = QPen(QColor(60, 68, 84), 1.2)
            else:
                bg_color = QColor(24, 28, 36)
                border_pen = QPen(QColor(44, 50, 64), 1.0)
        else:
            if self.is_selected:
                bg_color = QColor(234, 250, 246)
                border_pen = QPen(QColor(r, g, b), 1.8)
            elif self._is_hovered:
                bg_color = QColor(242, 245, 250)
                border_pen = QPen(QColor(180, 186, 198), 1.2)
            else:
                bg_color = QColor(255, 255, 255)
                border_pen = QPen(QColor(216, 221, 232), 1.0)

        painter.fillPath(path, bg_color)
        painter.setPen(border_pen)
        painter.drawPath(path)

        # Draw Indicator Circle (Top-Right)
        circle_x = w - 18
        circle_y = 18
        circle_r = 7.0

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
            ring_color = QColor(74, 82, 96) if dark else QColor(176, 182, 196)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring_color, 1.4))
            painter.drawEllipse(QPointF(circle_x, circle_y), circle_r, circle_r)

        painter.end()


class FormatCardSelector(QWidget):
    """Container grouping all format cards in a sleek horizontal row."""

    format_changed = Signal(str)  # emits format key ("WAV", "MP3", "MP4", etc.)

    def __init__(
        self,
        default_format: str = "WAV",
        formats: Optional[List[str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.selected_format = default_format
        self.allowed_formats = formats or ["WAV", "MP3", "MP4", "FLAC", "M4A"]
        self.cards: Dict[str, FormatCard] = {}

        self._setup_ui()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 5 Cards in a Single Horizontal Row matching 02_download_view.png
        cards_layout = QHBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)

        for item in FORMAT_DEFINITIONS:
            if item["key"] in self.allowed_formats:
                card = FormatCard(item, self)
                card.clicked.connect(self._on_card_clicked)
                self.cards[item["key"]] = card
                cards_layout.addWidget(card, 1)

        main_layout.addLayout(cards_layout)
        self.set_format(self.selected_format)

    def _on_card_clicked(self, key: str):
        self.set_format(key)

    def set_format(self, key: str):
        key = key.upper()
        if key not in self.cards:
            key = list(self.cards.keys())[0] if self.cards else "WAV"

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
