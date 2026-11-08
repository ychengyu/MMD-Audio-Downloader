"""
Task Card Component for MMD Audio Downloader.
Displays real-time progress, speed, ETA, MMD compatibility badge, and file action buttons
with modern Windows 11 Fluent Design.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.task_manager import TaskItem, TaskStatus, TaskType
from core.utils import format_bytes, format_speed, format_time
from ui.theme import ThemeManager, hex_to_rgb


class TaskCard(QFrame):
    """Visual card representing a background download or conversion task."""

    cancel_clicked = Signal(str)
    retry_clicked = Signal(str)
    remove_clicked = Signal(str)
    play_clicked = Signal(str)  # Emits file path to play

    def __init__(self, task: TaskItem, parent=None):
        super().__init__(parent)
        self.task = task
        self.setProperty("class", "card")
        self._setup_ui()
        self.update_task(task)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(6)

        # Row 1: Header (Type badge, Mode badge, Title, Action Buttons)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.type_badge = QLabel(self.task.task_type.value)
        self.type_badge.setStyleSheet(
            "background-color: rgba(100, 120, 150, 0.2); border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;"
        )
        top_layout.addWidget(self.type_badge)

        self.mode_badge = QLabel(self.task.target_format)
        accent = ThemeManager().accent_color
        r, g, b = hex_to_rgb(accent)
        self.mode_badge.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, 0.15); color: {accent}; border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;"
        )
        top_layout.addWidget(self.mode_badge)

        self.title_label = QLabel(self.task.title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.title_label.setWordWrap(True)
        top_layout.addWidget(self.title_label, 1)

        self.pct_label = QLabel("0%")
        self.pct_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_layout.addWidget(self.pct_label)

        # Control Buttons
        self.play_btn = QPushButton("▶ 試聽")
        self.play_btn.setMaximumWidth(70)
        self.play_btn.setVisible(False)

        self.open_file_btn = QPushButton("開啟檔案")
        self.open_file_btn.setMaximumWidth(80)
        self.open_file_btn.setVisible(False)

        self.open_folder_btn = QPushButton("開啟資料夾")
        self.open_folder_btn.setMaximumWidth(90)
        self.open_folder_btn.setVisible(False)

        self.retry_btn = QPushButton("重試")
        self.retry_btn.setMaximumWidth(60)
        self.retry_btn.setVisible(False)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setProperty("class", "danger")
        self.cancel_btn.setMaximumWidth(60)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setMaximumWidth(30)
        self.remove_btn.setToolTip("從清單中移除")

        top_layout.addWidget(self.play_btn)
        top_layout.addWidget(self.open_file_btn)
        top_layout.addWidget(self.open_folder_btn)
        top_layout.addWidget(self.retry_btn)
        top_layout.addWidget(self.cancel_btn)
        top_layout.addWidget(self.remove_btn)
        main_layout.addLayout(top_layout)

        # Row 2: Sleek Thin Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Row 3: Status & Message footer
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("等候中...")
        self.status_label.setStyleSheet("color: #A3AAB8; font-size: 11px;")
        bottom_layout.addWidget(self.status_label, 1)

        self.mmd_badge = QLabel("")
        self.mmd_badge.setVisible(False)
        bottom_layout.addWidget(self.mmd_badge, 0, Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(bottom_layout)

        # Signals
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.task.task_id))
        self.retry_btn.clicked.connect(lambda: self.retry_clicked.emit(self.task.task_id))
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.task.task_id))
        self.open_file_btn.clicked.connect(self._open_file)
        self.open_folder_btn.clicked.connect(self._open_folder)
        self.play_btn.clicked.connect(lambda: self.play_clicked.emit(self.task.output_file))

    def update_task(self, task: TaskItem):
        self.task = task
        self.title_label.setText(task.title or Path(task.source).name or "任務")

        if task.mode == "mmd_wav":
            self.mode_badge.setText("MMD 相容 WAV")
        elif task.mode == "video":
            self.mode_badge.setText(f"{task.target_format} (完整影片)")
        else:
            self.mode_badge.setText(f"{task.target_format} ({task.audio_quality})")

        pct = int(task.progress)
        self.progress_bar.setValue(pct)
        self.pct_label.setText(f"{pct}%")

        accent = ThemeManager().accent_color

        # Status text with speed and ETA if available
        if task.status == TaskStatus.RUNNING:
            if task.speed > 0:
                speed_str = format_speed(task.speed)
                eta_str = format_time(task.eta) if task.eta else "計算中..."
                msg = f"↓ {speed_str}  |  剩餘時間：{eta_str}"
                self.status_label.setText(msg)
            else:
                self.status_label.setText(task.message or "處理中...")
            self.cancel_btn.setVisible(True)
            self.retry_btn.setVisible(False)
            self.open_file_btn.setVisible(False)
            self.open_folder_btn.setVisible(False)
            self.play_btn.setVisible(False)
            self.status_label.setStyleSheet(f"color: {accent}; font-size: 11px; font-weight: 500;")

        elif task.status == TaskStatus.COMPLETED:
            self.status_label.setText(task.message or "✔ 下載與轉檔完成")
            self.cancel_btn.setVisible(False)
            self.retry_btn.setVisible(False)
            self.open_file_btn.setVisible(True)
            self.open_folder_btn.setVisible(True)
            self.play_btn.setVisible(bool(task.output_file and Path(task.output_file).exists()))
            self.status_label.setStyleSheet("color: #00E676; font-size: 11px; font-weight: 500;")

            if getattr(task, "is_mmd_valid", False):
                self.mmd_badge.setText("★ MMD 100% 相容")
                self.mmd_badge.setStyleSheet("color: #00E676; font-weight: bold; font-size: 11px;")
                self.mmd_badge.setVisible(True)

        elif task.status == TaskStatus.FAILED:
            self.status_label.setText(f"✕ 失敗: {task.error_message or task.message}")
            self.cancel_btn.setVisible(False)
            self.retry_btn.setVisible(True)
            self.open_file_btn.setVisible(False)
            self.open_folder_btn.setVisible(False)
            self.play_btn.setVisible(False)
            self.status_label.setStyleSheet("color: #FF5252; font-size: 11px;")

        elif task.status == TaskStatus.CANCELLED:
            self.status_label.setText("已由使用者取消")
            self.cancel_btn.setVisible(False)
            self.retry_btn.setVisible(True)
            self.open_file_btn.setVisible(False)
            self.open_folder_btn.setVisible(False)
            self.play_btn.setVisible(False)
            self.status_label.setStyleSheet("color: #A3AAB8; font-size: 11px;")

    def _open_file(self):
        if self.task.output_file and Path(self.task.output_file).exists():
            if sys.platform == "win32":
                os.startfile(self.task.output_file)
            else:
                subprocess.Popen(["xdg-open", self.task.output_file])

    def _open_folder(self):
        if self.task.output_file:
            folder = Path(self.task.output_file).parent
            if folder.exists():
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer /select,"{self.task.output_file}"')
                else:
                    subprocess.Popen(["xdg-open", str(folder)])
