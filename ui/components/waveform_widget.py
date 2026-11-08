"""
Waveform Widget for MMD Audio Downloader.
Displays audio peak bars, playback scrubber, and trim regions.
"""

from typing import List, Optional
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    """Interactive audio waveform viewer and scrubber."""

    seek_requested = Signal(float)  # Emits normalized position (0.0 to 1.0)
    trim_start_changed = Signal(float)
    trim_end_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: List[float] = []
        self.playback_pos: float = 0.0  # 0.0 to 1.0
        self.trim_start: Optional[float] = None  # 0.0 to 1.0
        self.trim_end: Optional[float] = None    # 0.0 to 1.0
        self.total_duration: float = 0.0

        self.setMinimumHeight(64)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: transparent;")

    def set_peaks(self, peaks: List[float], duration: float = 0.0) -> None:
        self.peaks = peaks
        self.total_duration = duration
        self.playback_pos = 0.0
        self.update()

    def set_playback_pos(self, pos: float) -> None:
        self.playback_pos = max(0.0, min(1.0, pos))
        self.update()

    def set_trim_range(self, start: Optional[float], end: Optional[float]) -> None:
        self.trim_start = start
        self.trim_end = end
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.width() > 0:
            norm_x = max(0.0, min(1.0, event.position().x() / self.width()))
            self.seek_requested.emit(norm_x)
            self.playback_pos = norm_x
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self.width() > 0:
            norm_x = max(0.0, min(1.0, event.position().x() / self.width()))
            self.seek_requested.emit(norm_x)
            self.playback_pos = norm_x
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2.0

        # Background box
        bg_rect = QRectF(0, 0, w, h)
        painter.fillRect(bg_rect, QColor(24, 27, 33, 180))

        # Trim shaded regions (outside trimmed range)
        if self.trim_start is not None and self.trim_start > 0:
            left_trim_w = self.trim_start * w
            painter.fillRect(QRectF(0, 0, left_trim_w, h), QColor(0, 0, 0, 120))

        if self.trim_end is not None and self.trim_end < 1.0:
            right_trim_x = self.trim_end * w
            painter.fillRect(QRectF(right_trim_x, 0, w - right_trim_x, h), QColor(0, 0, 0, 120))

        # Draw waveform bars
        if not self.peaks:
            # Placeholder flat line
            painter.setPen(QPen(QColor(80, 85, 100), 1))
            painter.drawLine(0, int(mid_y), w, int(mid_y))
            # Text prompt
            painter.setPen(QColor(120, 130, 150))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, "載入音訊後將在此顯示波形預覽")
            return

        num_bars = len(self.peaks)
        bar_w = max(1.5, (w / float(num_bars)) - 1.0)
        played_x = self.playback_pos * w

        for i, val in enumerate(self.peaks):
            x = (i / float(num_bars)) * w
            bar_h = max(2.0, val * (h - 12))
            top_y = mid_y - (bar_h / 2.0)

            # Different color for played vs unplayed
            if x <= played_x:
                color = QColor(0, 225, 205, 230)  # Bright cyan played
            else:
                color = QColor(90, 110, 130, 160)  # Subtle muted slate unplayed

            painter.fillRect(QRectF(x, top_y, bar_w, bar_h), color)

        # Draw Scrubber Line
        painter.setPen(QPen(QColor(255, 255, 255, 240), 2))
        painter.drawLine(int(played_x), 0, int(played_x), h)

        # Scrubber handle circle
        painter.setBrush(QBrush(QColor(0, 240, 220)))
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.drawEllipse(QPointF(played_x, mid_y), 4.5, 4.5)
