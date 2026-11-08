"""
Animated Stacked Widget for MMD Audio Downloader.
Provides smooth, lightweight fade-in transitions between views without blocking or flickering.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QWidget


class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget subclass featuring smooth micro-fade view transitions."""

    def __init__(self, parent=None, duration: int = 180):
        super().__init__(parent)
        self.duration = duration
        self._current_anim: QPropertyAnimation = None

    def set_current_index_animated(self, index: int):
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return

        # Stop previous animation if still running
        if self._current_anim and self._current_anim.state() == QPropertyAnimation.State.Running:
            self._current_anim.stop()

        target_widget = self.widget(index)
        if not target_widget:
            self.setCurrentIndex(index)
            return

        # Set up opacity effect on target widget
        effect = target_widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(target_widget)
            target_widget.setGraphicsEffect(effect)

        effect.setOpacity(0.35)
        self.setCurrentIndex(index)

        self._current_anim = QPropertyAnimation(effect, b"opacity")
        self._current_anim.setDuration(self.duration)
        self._current_anim.setStartValue(0.35)
        self._current_anim.setEndValue(1.0)
        self._current_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._current_anim.finished.connect(lambda w=target_widget: self._on_anim_finished(w))
        self._current_anim.start()

    def _on_anim_finished(self, widget: QWidget):
        if widget and widget.graphicsEffect():
            widget.setGraphicsEffect(None)
