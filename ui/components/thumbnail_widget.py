"""
Thread-safe, Cached Video Thumbnail Widget for MMD Audio Downloader.
Displays media thumbnails with rounded corners, aspect-ratio preservation,
loading state, error recovery, and hotlinking-safe background fetching.
"""

from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ThumbnailFetchWorker(QThread):
    """Background worker to download thumbnail image bytes safely without blocking GUI."""

    success = Signal(QImage, str)  # image, request_url
    failed = Signal(str, str)      # error_msg, request_url

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.url or self._is_cancelled:
            return

        try:
            import requests

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": "https://www.youtube.com/",
            }

            resp = requests.get(self.url, headers=headers, timeout=10)
            if self._is_cancelled:
                return

            if resp.status_code == 200 and resp.content:
                img = QImage()
                if img.loadFromData(resp.content):
                    self.success.emit(img, self.url)
                    return
                else:
                    self.failed.emit("無法解碼圖片資料", self.url)
            else:
                self.failed.emit(f"HTTP 回應碼: {resp.status_code}", self.url)

        except Exception as e:
            if not self._is_cancelled:
                self.failed.emit(str(e), self.url)


class ThumbnailWidget(QFrame):
    """Visual widget displaying video thumbnail with rounded corners and loading states."""

    _cache: Dict[str, QPixmap] = {}

    def __init__(self, width: int = 220, height: int = 124, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.target_w = width
        self.target_h = height
        self._current_url: str = ""
        self._worker: Optional[ThumbnailFetchWorker] = None
        self._pixmap: Optional[QPixmap] = None
        self.duration_text: str = ""

        self._setup_ui()
        self.show_placeholder()

    def _setup_ui(self):
        self.setObjectName("thumbnail_frame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_icon = QLabel("🎬")
        self.status_icon.setStyleSheet("font-size: 24px;")
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_text = QLabel("等待影片網址...")
        self.status_text.setStyleSheet("color: #8C95A6; font-size: 11px;")
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_text.setWordWrap(True)

        self.retry_btn = QPushButton("重新嘗試")
        self.retry_btn.setMaximumWidth(90)
        self.retry_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        self.retry_btn.setVisible(False)
        self.retry_btn.clicked.connect(self._retry_load)

        layout.addWidget(self.status_icon)
        layout.addWidget(self.status_text)
        layout.addWidget(self.retry_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def load_url(self, url: str):
        """Set thumbnail URL and start asynchronous background download."""
        if not url:
            self.show_placeholder()
            return

        self._current_url = url

        # Check in-memory cache first
        if url in self._cache:
            self._pixmap = self._cache[url]
            self._apply_pixmap()
            return

        # Show loading state
        self._pixmap = None
        self.status_icon.setVisible(True)
        self.status_icon.setText("⏳")
        self.status_text.setVisible(True)
        self.status_text.setText("正在載入縮圖...")
        self.retry_btn.setVisible(False)
        self.update()

        # Cancel previous worker if any
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(100)

        self._worker = ThumbnailFetchWorker(url)
        self._worker.success.connect(self._on_fetch_success)
        self._worker.failed.connect(self._on_fetch_failed)
        self._worker.start()

    def show_placeholder(self):
        """Reset to initial empty placeholder state."""
        self._current_url = ""
        self._pixmap = None
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.status_icon.setVisible(True)
        self.status_icon.setText("🎬")
        self.status_text.setVisible(True)
        self.status_text.setText("等待影片解析...")
        self.retry_btn.setVisible(False)
        self.update()

    def set_duration(self, duration_str: str):
        """Set duration string (e.g. '02:45') to render as an overlay badge."""
        self.duration_text = duration_str or ""
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        """Directly set a pixmap."""
        scaled_pix = pixmap.scaled(
            self.target_w,
            self.target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        crop_x = max(0, (scaled_pix.width() - self.target_w) // 2)
        crop_y = max(0, (scaled_pix.height() - self.target_h) // 2)
        cropped_pix = scaled_pix.copy(crop_x, crop_y, self.target_w, self.target_h)
        self._pixmap = self._create_rounded_pixmap(cropped_pix, radius=8)
        self._apply_pixmap()

    def clear(self):
        self.duration_text = ""
        self.show_placeholder()

    def _on_fetch_success(self, img: QImage, req_url: str):
        # Prevent race condition if user changed URL in the meantime
        if req_url != self._current_url:
            return

        # Create rounded pixmap
        raw_pix = QPixmap.fromImage(img)
        scaled_pix = raw_pix.scaled(
            self.target_w,
            self.target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

        # Center crop to exact widget size
        crop_x = max(0, (scaled_pix.width() - self.target_w) // 2)
        crop_y = max(0, (scaled_pix.height() - self.target_h) // 2)
        cropped_pix = scaled_pix.copy(crop_x, crop_y, self.target_w, self.target_h)

        # Apply rounded corner clipping
        rounded_pix = self._create_rounded_pixmap(cropped_pix, radius=10)
        self._cache[req_url] = rounded_pix
        self._pixmap = rounded_pix
        self._apply_pixmap()

    def _create_rounded_pixmap(self, src: QPixmap, radius: int = 10) -> QPixmap:
        dest = QPixmap(src.size())
        dest.fill(Qt.GlobalColor.transparent)

        painter = QPainter(dest)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, src.width(), src.height(), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src)
        painter.end()

        return dest

    def _apply_pixmap(self):
        self.status_icon.setVisible(False)
        self.status_text.setVisible(False)
        self.retry_btn.setVisible(False)
        self.update()

    def _on_fetch_failed(self, err: str, req_url: str):
        if req_url != self._current_url:
            return
        self._pixmap = None
        self.status_icon.setVisible(True)
        self.status_icon.setText("🖼️")
        self.status_text.setVisible(True)
        self.status_text.setText("無法載入縮圖")
        self.retry_btn.setVisible(True)
        self.update()

    def _retry_load(self):
        if self._current_url:
            self.load_url(self._current_url)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pixmap:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.drawPixmap(0, 0, self._pixmap)

            # Draw bottom-right duration badge if available
            if self.duration_text:
                font = painter.font()
                font.setPointSize(10)
                font.setBold(True)
                painter.setFont(font)

                metrics = painter.fontMetrics()
                text_w = metrics.horizontalAdvance(self.duration_text)
                text_h = metrics.height()

                pad_x = 6
                pad_y = 2
                badge_w = text_w + pad_x * 2
                badge_h = text_h + pad_y * 2
                badge_x = self.width() - badge_w - 6
                badge_y = self.height() - badge_h - 6

                # Black rounded background
                badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
                badge_path = QPainterPath()
                badge_path.addRoundedRect(badge_rect, 4, 4)
                painter.fillPath(badge_path, QColor(0, 0, 0, 205))

                # Crisp white text
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.duration_text)
