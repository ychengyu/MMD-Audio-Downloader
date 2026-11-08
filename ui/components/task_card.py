"""
Task Card Component for MMD Audio Downloader.
Displays real-time progress, speed, ETA, MMD compatibility badge, and file action buttons
with modern Windows 11 Fluent Design matching reference 04_task_manager_view.png.
"""

import os
import subprocess
import sys
import time
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
from ui.theme import ThemeManager, adjust_color, hex_to_rgb


class TaskCard(QFrame):
    """Visual card representing a background download or conversion task matching 04_task_manager_view.png."""

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
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 16, 12)
        main_layout.setSpacing(14)

        # 1. Left Media Thumbnail / Icon
        self.thumb_box = QLabel("🎵")
        self.thumb_box.setFixedSize(54, 54)
        self.thumb_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_box.setStyleSheet("""
            QLabel {
                background-color: #1A1E26;
                color: #00D2B4;
                font-size: 24px;
                border: 1px solid #282E3D;
                border-radius: 8px;
            }
        """)
        main_layout.addWidget(self.thumb_box)

        # 2. Middle Details Column
        mid_col = QVBoxLayout()
        mid_col.setContentsMargins(0, 0, 0, 0)
        mid_col.setSpacing(4)

        # Row 1: Badges
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)

        self.type_badge = QLabel("影音下載")
        self.type_badge.setStyleSheet("""
            QLabel {
                background-color: #212631;
                color: #A3AAB8;
                border-radius: 4px;
                padding: 1px 7px;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        badge_row.addWidget(self.type_badge)

        self.mode_badge = QLabel("MMD 格式 WAV")
        self.mode_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 210, 180, 0.12);
                color: #00D2B4;
                border-radius: 4px;
                padding: 1px 7px;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        badge_row.addWidget(self.mode_badge)
        badge_row.addStretch(1)
        mid_col.addLayout(badge_row)

        # Row 2: Title
        self.title_label = QLabel(self.task.title or "任務名稱")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        self.title_label.setWordWrap(False)
        mid_col.addWidget(self.title_label)

        # Row 3: Subtitle / Source URL
        self.sub_label = QLabel(self.task.source or "")
        self.sub_label.setStyleSheet("font-size: 12px; color: #8E95A5; background: transparent;")
        mid_col.addWidget(self.sub_label)

        # Row 4: Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1F232D;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #00D2B4;
                border-radius: 2px;
            }
        """)
        mid_col.addWidget(self.progress_bar)

        # Row 5: Status text + Verification Pill
        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        self.status_label = QLabel("等候中...")
        self.status_label.setStyleSheet("color: #8E95A5; font-size: 11px; background: transparent;")
        status_row.addWidget(self.status_label)

        self.verify_pill = QLabel("✓ MMD 格式音訊 (44.1 kHz / 16-bit PCM / Stereo)")
        self.verify_pill.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 230, 118, 0.12);
                color: #00E676;
                border: 1px solid rgba(0, 230, 118, 0.3);
                border-radius: 10px;
                padding: 1px 9px;
                font-size: 10px;
                font-weight: 600;
            }
        """)
        self.verify_pill.setVisible(False)
        status_row.addWidget(self.verify_pill)
        status_row.addStretch(1)

        mid_col.addLayout(status_row)
        main_layout.addLayout(mid_col, 1)

        # 3. Right Action Buttons Column
        right_box = QHBoxLayout()
        right_box.setSpacing(8)
        right_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.detail_btn = QPushButton("ⓘ 詳細")
        self.detail_btn.setFixedHeight(30)
        self.detail_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")

        self.retry_btn = QPushButton("🔄 重新下載")
        self.retry_btn.setFixedHeight(30)
        self.retry_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.retry_btn.clicked.connect(lambda: self.retry_clicked.emit(self.task.task_id))

        self.open_folder_btn = QPushButton("📁 開啟資料夾")
        self.open_folder_btn.setFixedHeight(30)
        self.open_folder_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.open_folder_btn.clicked.connect(self._open_folder)

        self.cancel_btn = QPushButton("✕ 取消")
        self.cancel_btn.setFixedHeight(30)
        self.cancel_btn.setProperty("class", "danger")
        self.cancel_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.task.task_id))

        right_box.addWidget(self.detail_btn)
        right_box.addWidget(self.retry_btn)
        right_box.addWidget(self.open_folder_btn)
        right_box.addWidget(self.cancel_btn)
        main_layout.addLayout(right_box)

    def update_task(self, task: TaskItem):
        self.task = task
        self.title_label.setText(task.title or Path(task.source).name or "任務")
        self.sub_label.setText(task.source or "")

        # Update Thumbnail Icon
        is_video = (task.mode == "video" or task.target_format.upper() in ("MP4", "MKV", "WEBM"))
        self.thumb_box.setText("🎞" if is_video else "🎵")

        # Update Badges
        if task.task_type == TaskType.DOWNLOAD:
            self.type_badge.setText("影音下載")
        else:
            self.type_badge.setText("格式轉換")

        if task.mode == "mmd_wav":
            self.mode_badge.setText("MMD 格式 WAV")
        else:
            self.mode_badge.setText(f"{task.target_format.upper()} 格式")

        pct = int(task.progress)
        self.progress_bar.setValue(pct)

        # Status & Message text
        if task.status == TaskStatus.RUNNING:
            spd_str = format_speed(task.speed) if task.speed > 0 else ""
            eta_str = format_time(task.eta) if task.eta > 0 else ""
            if spd_str and eta_str:
                self.status_label.setText(f"下載中... {pct}% · ↓ {spd_str} · 剩餘時間 {eta_str}")
            elif task.message:
                self.status_label.setText(f"{task.message} ({pct}%)")
            else:
                self.status_label.setText(f"處理中... {pct}%")

            self.cancel_btn.setVisible(True)
            self.retry_btn.setVisible(False)
            self.open_folder_btn.setVisible(False)
            self.verify_pill.setVisible(False)

        elif task.status == TaskStatus.COMPLETED:
            finish_time = time.strftime("%Y/%m/%d %H:%M", time.localtime(task.finished_at)) if task.finished_at else ""
            sz_str = format_bytes(task.downloaded_bytes or task.total_bytes) if (task.downloaded_bytes or task.total_bytes) else ""
            meta_parts = ["✓ 已完成"]
            if finish_time:
                meta_parts.append(finish_time)
            if sz_str:
                meta_parts.append(sz_str)
            self.status_label.setText(" · ".join(meta_parts))

            self.cancel_btn.setVisible(False)
            self.retry_btn.setVisible(False)
            self.open_folder_btn.setVisible(True)

            if task.mode == "mmd_wav":
                self.verify_pill.setVisible(True)
                if task.is_mmd_valid:
                    self.verify_pill.setText("✓ MMD 格式音訊 (44.1 kHz / 16-bit PCM / Stereo)")
                else:
                    self.verify_pill.setText("✓ 音訊已轉碼完成")
            else:
                self.verify_pill.setVisible(False)

        elif task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            err_msg = task.error_message or task.message or ("已取消" if task.status == TaskStatus.CANCELLED else "失敗")
            self.status_label.setText(f"✕ {err_msg}")
            self.cancel_btn.setVisible(False)
            self.retry_btn.setVisible(True)
            self.open_folder_btn.setVisible(False)
            self.verify_pill.setVisible(False)

        else:
            self.status_label.setText("佇列等候中...")
            self.cancel_btn.setVisible(True)
            self.retry_btn.setVisible(False)
            self.open_folder_btn.setVisible(False)
            self.verify_pill.setVisible(False)

    def _open_folder(self):
        folder = self.task.output_dir
        if self.task.output_file and Path(self.task.output_file).exists():
            p = Path(self.task.output_file)
            if sys.platform == "win32":
                subprocess.Popen(f'explorer /select,"{p}"')
                return
        if folder and Path(folder).exists():
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])

    def _on_theme_changed(self, mode: str, accent: str):
        is_dark = (mode == "dark")
        text_pri = "#FFFFFF" if is_dark else "#181A20"
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_pri}; background: transparent;")
