"""
Task Manager View for MMD Audio Downloader.
Displays real-time queue, speed, status filters, history, and task management actions.
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
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.task_manager import TaskItem, TaskManager, TaskStatus
from ui.components.empty_state import EmptyStateWidget
from ui.components.task_card import TaskCard
from ui.components.toast import ToastManager, ToastType


class TaskManagerView(QWidget):
    """View managing active and historical tasks."""

    play_audio_requested = Signal(str)

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.card_widgets: Dict[str, TaskCard] = {}
        self.current_filter = "ALL"  # "ALL", "RUNNING", "COMPLETED", "FAILED"

        self._setup_ui()
        self._connect_signals()
        self._refresh_all_cards()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header Control Bar
        header_card = QFrame()
        header_card.setProperty("class", "card")
        header_layout = QHBoxLayout(header_card)

        # Stat labels
        self.stats_label = QLabel("任務狀態: 0 執行中 | 0 已完成 | 0 失敗")
        self.stats_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(self.stats_label)

        header_layout.addStretch(1)

        self.open_folder_btn = QPushButton("📂 開啟下載資料夾")
        self.clear_btn = QPushButton("清空已完成")
        self.export_btn = QPushButton("匯出紀錄")

        header_layout.addWidget(self.open_folder_btn)
        header_layout.addWidget(self.clear_btn)
        header_layout.addWidget(self.export_btn)
        main_layout.addWidget(header_card)

        # Filter Tabs
        filter_bar = QHBoxLayout()
        self.filter_group = QButtonGroup(self)

        self.btn_all = QPushButton("全部任務")
        self.btn_running = QPushButton("執行中")
        self.btn_completed = QPushButton("已完成")
        self.btn_failed = QPushButton("失敗／取消")

        for b in [self.btn_all, self.btn_running, self.btn_completed, self.btn_failed]:
            b.setCheckable(True)
            self.filter_group.addButton(b)
            filter_bar.addWidget(b)

        self.btn_all.setChecked(True)
        filter_bar.addStretch(1)
        main_layout.addLayout(filter_bar)

        # Scrollable Task Cards Container
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)

        # Empty State
        self.empty_state = EmptyStateWidget(
            icon_text="📋",
            title="目前尚無排程或歷史任務",
            description="您可以從『★ MMD WAV 專區』快速轉換音樂，或從『📥 影音下載』貼上網址開始下載！",
            action_text="前往 ★ MMD WAV 專區",
            action_callback=lambda: self.play_audio_requested.emit("__nav_mmd__")
        )
        self.cards_layout.addWidget(self.empty_state)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll, 1)

    def _connect_signals(self):
        self.task_manager.signals.task_added.connect(self._on_task_added)
        self.task_manager.signals.task_updated.connect(self._on_task_updated)
        self.task_manager.signals.task_completed.connect(self._on_task_completed)
        self.task_manager.signals.task_failed.connect(self._on_task_failed)
        self.task_manager.signals.task_cancelled.connect(self._on_task_cancelled)
        self.task_manager.signals.queue_cleared.connect(self._on_queue_cleared)

        self.btn_all.clicked.connect(lambda: self._set_filter("ALL"))
        self.btn_running.clicked.connect(lambda: self._set_filter("RUNNING"))
        self.btn_completed.clicked.connect(lambda: self._set_filter("COMPLETED"))
        self.btn_failed.clicked.connect(lambda: self._set_filter("FAILED"))

        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.clear_btn.clicked.connect(self._clear_completed)
        self.export_btn.clicked.connect(self._export_history)

    def _set_filter(self, filter_name: str):
        self.current_filter = filter_name
        self._apply_filter()

    def _apply_filter(self):
        visible_count = 0
        for tid, card in self.card_widgets.items():
            status = card.task.status
            is_vis = True
            if self.current_filter == "ALL":
                is_vis = True
            elif self.current_filter == "RUNNING":
                is_vis = (status == TaskStatus.RUNNING or status == TaskStatus.PENDING)
            elif self.current_filter == "COMPLETED":
                is_vis = (status == TaskStatus.COMPLETED)
            elif self.current_filter == "FAILED":
                is_vis = (status in (TaskStatus.FAILED, TaskStatus.CANCELLED))
            card.setVisible(is_vis)
            if is_vis:
                visible_count += 1

        self.empty_state.setVisible(visible_count == 0)

    def _on_task_added(self, task_id: str):
        task = self.task_manager.tasks.get(task_id)
        if not task:
            return

        card = TaskCard(task)
        card.cancel_clicked.connect(self.task_manager.cancel_task)
        card.retry_clicked.connect(self.task_manager.retry_task)
        card.remove_clicked.connect(self._remove_card)
        card.play_clicked.connect(self.play_audio_requested.emit)

        self.card_widgets[task_id] = card
        # Insert at top of list
        self.cards_layout.insertWidget(0, card)
        self._update_stats()
        self._apply_filter()

    def _on_task_updated(self, task_id: str):
        task = self.task_manager.tasks.get(task_id)
        card = self.card_widgets.get(task_id)
        if task and card:
            card.update_task(task)
        self._update_stats()

    def _on_task_completed(self, task_id: str):
        self._on_task_updated(task_id)

    def _on_task_failed(self, task_id: str, err: str):
        self._on_task_updated(task_id)

    def _on_task_cancelled(self, task_id: str):
        self._on_task_updated(task_id)

    def _remove_card(self, task_id: str):
        self.task_manager.remove_task(task_id)
        card = self.card_widgets.pop(task_id, None)
        if card:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._update_stats()

    def _clear_completed(self):
        self.task_manager.clear_completed()

    def _on_queue_cleared(self):
        to_del = [tid for tid, card in self.card_widgets.items() if card.task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)]
        for tid in to_del:
            card = self.card_widgets.pop(tid, None)
            if card:
                self.cards_layout.removeWidget(card)
                card.deleteLater()
        self._update_stats()

    def _refresh_all_cards(self):
        all_tasks = self.task_manager.get_all_tasks()
        # Sort tasks: running/pending first, then by created_at desc
        all_tasks.sort(key=lambda t: t.created_at, reverse=False)
        for t in all_tasks:
            self._on_task_added(t.task_id)

    def _update_stats(self):
        tasks = self.task_manager.get_all_tasks()
        running = sum(1 for t in tasks if t.status in (TaskStatus.RUNNING, TaskStatus.PENDING))
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED))

        self.stats_label.setText(f"任務狀態: {running} 執行中 | {completed} 已完成 | {failed} 失敗/取消")

    def _open_output_folder(self):
        cfg = self.config_mgr.get()
        out_dir = cfg.output_dir
        if out_dir and os.path.exists(out_dir):
            if sys.platform == "win32":
                subprocess.Popen(f'explorer "{out_dir}"')
            else:
                subprocess.Popen(["xdg-open", out_dir])

    def _export_history(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出任務紀錄",
            "mmd_task_history.json",
            "JSON 檔案 (*.json);;所有檔案 (*.*)"
        )
        if path:
            try:
                tasks = self.task_manager.get_all_tasks()
                data = [{
                    "id": t.task_id,
                    "type": t.task_type.value,
                    "title": t.title,
                    "source": t.source,
                    "target_format": t.target_format,
                    "status": t.status.value,
                    "output_file": t.output_file,
                    "is_mmd_valid": t.is_mmd_valid,
                    "verification": t.verification_msg,
                    "details": t.media_details
                } for t in tasks]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                ToastManager.show_toast(
                    self,
                    title="匯出紀錄成功",
                    message=f"已成功儲存至: {Path(path).name}",
                    toast_type=ToastType.SUCCESS
                )
            except Exception as e:
                QMessageBox.critical(self, "匯出失敗", f"無法寫入檔案: {e}")
