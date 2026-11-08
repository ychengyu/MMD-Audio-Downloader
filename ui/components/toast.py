"""
Modern Windows 11 Fluent Toast Notification System for MMD Audio Downloader.
Provides non-blocking, beautifully animated feedback for user actions.
"""

from enum import Enum
from typing import Optional
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import ThemeManager, get_contrast_text_color, hex_to_rgb


class ToastType(Enum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ToastWidget(QFrame):
    """Individual floating toast card with icon, title, description, and close button."""

    def __init__(
        self,
        title: str,
        message: str = "",
        toast_type: ToastType = ToastType.INFO,
        duration_ms: int = 3500,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.toast_type = toast_type
        self.duration_ms = duration_ms

        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._setup_ui(title, message)
        self._setup_animations()

        # Auto-dismiss timer
        if duration_ms > 0:
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.fade_out_and_close)
            self.timer.start(duration_ms)

    def _setup_ui(self, title: str, message: str):
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Type Icon
        icons = {
            ToastType.SUCCESS: ("✓", "#00E676"),
            ToastType.INFO: ("ℹ", ThemeManager().accent_color),
            ToastType.WARNING: ("⚠", "#FFB300"),
            ToastType.ERROR: ("✕", "#FF5252"),
        }
        icon_char, self.accent_col = icons.get(self.toast_type, ("ℹ", ThemeManager().accent_color))

        self.icon_label = QLabel(icon_char)
        self.icon_label.setFixedSize(26, 26)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            background-color: {self.accent_col};
            color: #FFFFFF;
            font-size: 14px;
            font-weight: bold;
            border-radius: 13px;
        """)
        main_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # 2. Text layout
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.title_lbl.setWordWrap(True)
        text_layout.addWidget(self.title_lbl)

        if message:
            self.msg_lbl = QLabel(message)
            self.msg_lbl.setStyleSheet("font-size: 12px; color: #8A94A6;")
            self.msg_lbl.setWordWrap(True)
            text_layout.addWidget(self.msg_lbl)

        main_layout.addLayout(text_layout, 1)

        # 3. Dismiss button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #8C95A6;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                padding: 0px;
                min-height: 0px;
            }
            QPushButton:hover {
                background-color: rgba(150, 150, 150, 0.2);
                color: #FFFFFF;
            }
        """)
        self.close_btn.clicked.connect(self.fade_out_and_close)
        main_layout.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignTop)

    def _setup_animations(self):
        # Opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        # Fade in animation
        self.fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_anim.setDuration(220)
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(1.0)
        self.fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tm = ThemeManager()
        dark = tm.is_dark()

        w = self.width()
        h = self.height()
        path = QPainterPath()
        path.addRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        # Opaque surface
        bg_col = QColor(30, 34, 44) if dark else QColor(255, 255, 255)
        border_col = QColor(55, 62, 78) if dark else QColor(215, 220, 230)

        painter.fillPath(path, bg_col)
        painter.setPen(QPen(border_col, 1.2))
        painter.drawPath(path)

        super().paintEvent(event)

    def show_animated(self, target_pos: QPoint):
        self.move(target_pos)
        self.show()
        self.fade_in_anim.start()

    def fade_out_and_close(self):
        self.fade_out_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_anim.setDuration(180)
        self.fade_out_anim.setStartValue(self.opacity_effect.opacity())
        self.fade_out_anim.setEndValue(0.0)
        self.fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_anim.finished.connect(self.close)
        self.fade_out_anim.start()


class ToastManager:
    """Singleton manager coordinating floating toast queue in bottom-right corner."""

    _active_toasts: list[ToastWidget] = []

    @classmethod
    def show_toast(
        cls,
        parent: QWidget,
        title: str,
        message: str = "",
        toast_type: ToastType = ToastType.INFO,
        duration_ms: int = 3500
    ) -> ToastWidget:
        # Clean dead toasts
        cls._active_toasts = [t for t in cls._active_toasts if t.isVisible()]

        toast = ToastWidget(
            title=title,
            message=message,
            toast_type=toast_type,
            duration_ms=duration_ms,
            parent=parent
        )
        toast.adjustSize()

        # Compute position in bottom-right corner
        margin_x = 24
        margin_y = 24
        spacing = 10

        parent_geo = parent.geometry()
        x = parent.width() - toast.width() - margin_x
        y = parent.height() - toast.height() - margin_y

        # Stack upwards if multiple toasts
        for existing in cls._active_toasts:
            y -= (existing.height() + spacing)

        toast.show_animated(QPoint(max(10, x), max(10, y)))
        cls._active_toasts.append(toast)
        return toast
