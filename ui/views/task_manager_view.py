"""
Task Manager View for MMD Audio Downloader.
Displays real-time queue, speed, status filters, history, and task management actions
matching reference 04_task_manager_view.png.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.task_manager import TaskItem, TaskManager, TaskStatus
from ui.components.empty_state import EmptyStateWidget
from ui.components.hero_banner import HeroBannerWidget
from ui.components.task_card import TaskCard
from ui.components.toast import ToastManager, ToastType
from ui.theme import ThemeManager


class TaskManagerView(QWidget):
    """View managing active and historical tasks matching 04_task_manager_view.png."""

    play_audio_requested = Signal(str)

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.theme_mgr = ThemeManager()
        self.card_widgets: Dict[str, TaskCard] = {}
        self.current_filter = "ALL"  # "ALL", "RUNNING", "COMPLETED", "FAILED"

        self._setup_ui()
        self._connect_signals()
        self._refresh_all_cards()
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 1. Page Header matching 04_task_manager_view.png
        self.hero_banner = HeroBannerWidget(
            title="📋  任務管理",
            desc=[
                "即時監控所有背景下載與格式轉換任務，掌握傳輸進度、即時速率與剩餘時間。"
            ],
            badge_type="tasks"
        )
        main_layout.addWidget(self.hero_banner)

        # 2. Stats & Action Toolbar Card matching 04_task_manager_view.png
        stats_card = QFrame()
        stats_card.setProperty("class", "card")
        stats_layout = QHBoxLayout(stats_card)
        stats_layout.setContentsMargins(16, 10, 16, 10)
        stats_layout.setSpacing(12)

        # 3 Colored Status Badges on the left
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)

        self.pill_running = QLabel("▶ 執行中 0")
        self.pill_running.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 210, 180, 0.12);
                color: #00D2B4;
                border: 1px solid rgba(0, 210, 180, 0.35);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        self.pill_completed = QLabel("✓ 已完成 0")
        self.pill_completed.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 230, 118, 0.12);
                color: #00E676;
                border: 1px solid rgba(0, 230, 118, 0.35);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        self.pill_failed = QLabel("✕ 失敗/取消 0")
        self.pill_failed.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 82, 82, 0.12);
                color: #FF5252;
                border: 1px solid rgba(255, 82, 82, 0.35);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        badges_row.addWidget(self.pill_running)
        badges_row.addWidget(self.pill_completed)
        badges_row.addWidget(self.pill_failed)
        stats_layout.addLayout(badges_row)

        stats_layout.addStretch(1)

        # Right Action Buttons
        self.open_folder_btn = QPushButton("📁 開啟下載資料夾")
        self.open_folder_btn.setFixedHeight(32)
        self.clear_btn = QPushButton("🧹 清空已完成")
        self.clear_btn.setFixedHeight(32)
        self.export_btn = QPushButton("📄 匯出記錄")
        self.export_btn.setFixedHeight(32)

        stats_layout.addWidget(self.open_folder_btn)
        stats_layout.addWidget(self.clear_btn)
        stats_layout.addWidget(self.export_btn)
        main_layout.addWidget(stats_card)

        # 3. Filter Tabs Row matching 04_task_manager_view.png
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)
        self.filter_group = QButtonGroup(self)

        self.btn_all = QPushButton("全部任務")
        self.btn_running = QPushButton("執行中")
        self.btn_completed = QPushButton("已完成")
        self.btn_failed = QPushButton("失敗/取消")

        filter_buttons = [self.btn_all, self.btn_running, self.btn_completed, self.btn_failed]
        for b in filter_buttons:
            b.setCheckable(True)
            b.setFixedHeight(30)
            self.filter_group.addButton(b)
            filter_bar.addWidget(b)

        self.btn_all.setChecked(True)
        self._update_filter_styles()
        filter_bar.addStretch(1)
        main_layout.addLayout(filter_bar)

        # 4. Scrollable Task Cards Container
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)

        # Empty State
        self.empty_state = EmptyStateWidget(
            icon_text="📋",
            title="目前沒有任何任務",
            description="您可以前往「影音下載」下載網路影片，\n或至「MMD WAV 專區」轉換音訊檔案！",
            action_text="📥 前往影音下載",
            action_callback=lambda: self.play_audio_requested.emit("__nav_download__")
        )
        self.cards_layout.addWidget(self.empty_state)
        self.cards_layout.addStretch(1)

        self.scroll.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll, 1)

        # Connect actions
        self.open_folder_btn.clicked.connect(self._open_downloads_folder)
        self.clear_btn.clicked.connect(self._clear_completed)
        self.export_btn.clicked.connect(self._export_history)
        self.filter_group.buttonClicked.connect(self._on_filter_changed)

    def _connect_signals(self):
        sig = self.task_manager.signals
        sig.task_added.connect(self._on_task_added)
        sig.task_updated.connect(self._on_task_updated)
        sig.task_completed.connect(self._on_task_completed)
        sig.task_failed.connect(self._on_task_failed)
        sig.task_cancelled.connect(self._on_task_cancelled)

    def _update_filter_styles(self):
        accent = self.theme_mgr.accent_color
        for b in [self.btn_all, self.btn_running, self.btn_completed, self.btn_failed]:
            is_active = b.isChecked()
            if is_active:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {accent};
                        color: #0E151B;
                        font-weight: bold;
                        border-radius: 15px;
                        padding: 4px 16px;
                        font-size: 12px;
                        border: none;
                    }}
                """)
            else:
                b.setStyleSheet("""
                    QPushButton {{
                        background-color: #1A1E26;
                        color: #A3AAB8;
                        border: 1px solid #2B313F;
                        border-radius: 15px;
                        padding: 4px 16px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: #242A36;
                        color: #FFFFFF;
                        border: 1px solid #3D4658;
                    }}
                """)

    def _on_filter_changed(self, btn: QPushButton):
        self._update_filter_styles()
        if btn == self.btn_all:
            self.current_filter = "ALL"
        elif btn == self.btn_running:
            self.current_filter = "RUNNING"
        elif btn == self.btn_completed:
            self.current_filter = "COMPLETED"
        elif btn == self.btn_failed:
            self.current_filter = "FAILED"
        self._apply_filter()

    def _apply_filter(self):
        visible_count = 0
        for task_id, card in self.card_widgets.items():
            status = card.task.status
            should_show = False
            if self.current_filter == "ALL":
                should_show = True
            elif self.current_filter == "RUNNING" and status in (TaskStatus.RUNNING, TaskStatus.PENDING):
                should_show = True
            elif self.current_filter == "COMPLETED" and status == TaskStatus.COMPLETED:
                should_show = True
            elif self.current_filter == "FAILED" and status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                should_show = True

            card.setVisible(should_show)
            if should_show:
                visible_count += 1

        self.empty_state.setVisible(visible_count == 0)

    def _refresh_all_cards(self):
        tasks = self.task_manager.get_all_tasks()
        for t in tasks:
            self._add_or_update_card(t)
        self._update_stats_display()
        self._apply_filter()

    def _add_or_update_card(self, task: TaskItem):
        if task.task_id not in self.card_widgets:
            card = TaskCard(task, self.cards_container)
            card.cancel_clicked.connect(self.task_manager.cancel_task)
            card.retry_clicked.connect(self.task_manager.retry_task)
            card.remove_clicked.connect(self._remove_task_card)
            card.play_clicked.connect(self.play_audio_requested.emit)

            self.card_widgets[task.task_id] = card
            # Insert before empty_state and stretch
            self.cards_layout.insertWidget(0, card)
        else:
            self.card_widgets[task.task_id].update_task(task)

    def _remove_task_card(self, task_id: str):
        if task_id in self.card_widgets:
            card = self.card_widgets.pop(task_id)
            self.cards_layout.removeWidget(card)
            card.deleteLater()
            self.task_manager.remove_task(task_id)
            self._update_stats_display()
            self._apply_filter()

    def _update_stats_display(self):
        tasks = self.task_manager.get_all_tasks()
        running = len([t for t in tasks if t.status in (TaskStatus.RUNNING, TaskStatus.PENDING)])
        completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in tasks if t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED)])

        self.pill_running.setText(f"▶ 執行中 {running}")
        self.pill_completed.setText(f"✓ 已完成 {completed}")
        self.pill_failed.setText(f"✕ 失敗/取消 {failed}")

    def _on_task_added(self, task_id: str):
        task = self.task_manager.get_task(task_id)
        if task:
            self._add_or_update_card(task)
            self._update_stats_display()
            self._apply_filter()

    def _on_task_updated(self, task_id: str):
        task = self.task_manager.get_task(task_id)
        if task and task_id in self.card_widgets:
            self.card_widgets[task_id].update_task(task)
            self._update_stats_display()

    def _on_task_completed(self, task_id: str):
        self._on_task_updated(task_id)
        self._apply_filter()

    def _on_task_failed(self, task_id: str, err: str):
        self._on_task_updated(task_id)
        self._apply_filter()

    def _on_task_cancelled(self, task_id: str):
        self._on_task_updated(task_id)
        self._apply_filter()

    def _open_downloads_folder(self):
        cfg = self.config_mgr.get()
        out_dir = cfg.output_dir
        if out_dir and Path(out_dir).exists():
            if sys.platform == "win32":
                os.startfile(out_dir)
            else:
                subprocess.Popen(["xdg-open", out_dir])
        else:
            QMessageBox.warning(self, "資料夾不存在", f"找不到下載目錄:\n{out_dir}")

    def _clear_completed(self):
        tasks = self.task_manager.get_all_tasks()
        removed = 0
        for t in tasks:
            if t.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
                self._remove_task_card(t.task_id)
                removed += 1
        ToastManager.show_toast(
            self,
            title="已清理任務清單",
            message=f"已成功移除 {removed} 筆已完成或已結束的任務紀錄",
            toast_type=ToastType.INFO
        )

    def _export_history(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出任務記錄",
            "task_history.json",
            "JSON 檔案 (*.json);;所有檔案 (*.*)"
        )
        if file_path:
            tasks = [t.to_dict() for t in self.task_manager.get_all_tasks()]
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=2)
                ToastManager.show_toast(
                    self,
                    title="匯出成功",
                    message=f"已儲存任務記錄至:\n{Path(file_path).name}",
                    toast_type=ToastType.SUCCESS
                )
            except Exception as e:
                QMessageBox.critical(self, "匯出失敗", f"無法寫入檔案: {e}")

    def _on_theme_changed(self, mode: str, accent: str):
        self._update_filter_styles()
