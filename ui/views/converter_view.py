"""
Batch Local Media Converter View for MMD Audio Downloader.
Supports drag-and-drop batch addition of audio and video files,
media parameter inspection, format selection, and batch execution.
"""

from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.ffmpeg_engine import FFmpegEngine, MediaInfo
from core.task_manager import TaskManager
from core.utils import format_bytes, format_time
from ui.components.empty_state import EmptyStateWidget
from ui.components.toast import ToastManager, ToastType


class ProbeWorker(QThread):
    """Background worker that probes media files via ffprobe without freezing UI."""
    item_probed = Signal(int, Path, object)  # row_idx, file_path, MediaInfo or None

    def __init__(self, ffmpeg_engine: FFmpegEngine, paths: List[Path], start_row: int):
        super().__init__()
        self.ffmpeg_engine = ffmpeg_engine
        self.paths = paths
        self.start_row = start_row

    def run(self):
        for idx, p in enumerate(self.paths):
            info = None
            try:
                info = self.ffmpeg_engine.probe_media(p)
            except Exception:
                pass
            self.item_probed.emit(self.start_row + idx, p, info)


class ConverterView(QWidget):
    """View for converting local audio and video files in batch."""

    SUPPORTED_EXTS = {
        ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus",
        ".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".ts"
    }

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.ffmpeg_engine = self.task_manager.ffmpeg_engine

        self.file_items: List[Path] = []
        self.media_infos: Dict[str, MediaInfo] = {}

        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header card
        header_card = QFrame()
        header_card.setProperty("class", "card")
        header_layout = QHBoxLayout(header_card)

        info_box = QVBoxLayout()
        title = QLabel("本機影音格式批次轉換")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        subtitle = QLabel("支援 MP3、MP4、FLAC、M4A、OGG、WAV 等檔案批次轉換為 MMD WAV 或其他音訊格式。可直接拖曳檔案至下方表格！")
        subtitle.setStyleSheet("color: #8C95A6; font-size: 12px;")
        info_box.addWidget(title)
        info_box.addWidget(subtitle)
        header_layout.addLayout(info_box, 1)

        # Uniform target format selector
        fmt_box = QHBoxLayout()
        fmt_box.addWidget(QLabel("統一目標格式:"))
        self.batch_fmt_combo = QComboBox()
        self.batch_fmt_combo.addItems([
            "★ MMD 專用 WAV (44.1kHz 16-bit)",
            "WAV (標準 PCM)",
            "MP3 (320 kbps)",
            "MP3 (192 kbps)",
            "FLAC (無損音訊)",
            "M4A (AAC 256k)",
            "OGG (Vorbis)",
            "OPUS",
            "MP4 (影片容器)"
        ])
        fmt_box.addWidget(self.batch_fmt_combo)
        header_layout.addLayout(fmt_box)

        main_layout.addWidget(header_card)

        # Table Widget
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "檔案名稱", "格式/編碼", "採樣率", "聲道", "時長", "大小", "狀態"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        main_layout.addWidget(self.table, 1)

        # Empty state placeholder
        self.empty_state = EmptyStateWidget(
            icon_text="📂",
            title="尚未加入任何待轉檔檔案",
            description="您可以直接拖曳 MP3、MP4、FLAC、M4A、OGG、WAV 等檔案或資料夾至此視窗，\n或點選下方按鈕加入檔案進行批次轉檔！",
            action_text="📁 瀏覽加入本機檔案...",
            action_callback=self._on_add_files
        )
        main_layout.addWidget(self.empty_state, 1)
        self.empty_state.setVisible(True)
        self.table.setVisible(False)

        # Bottom Action Bar
        action_bar = QHBoxLayout()
        self.add_files_btn = QPushButton("📁 加入檔案...")
        self.add_folder_btn = QPushButton("📂 加入資料夾...")
        self.clear_btn = QPushButton("清空清單")
        self.convert_all_btn = QPushButton("⚡ 開始全部批次轉檔")
        self.convert_all_btn.setProperty("class", "primary")
        self.convert_all_btn.setMinimumHeight(40)
        self.convert_all_btn.setMinimumWidth(160)

        action_bar.addWidget(self.add_files_btn)
        action_bar.addWidget(self.add_folder_btn)
        action_bar.addWidget(self.clear_btn)
        action_bar.addStretch(1)
        action_bar.addWidget(self.convert_all_btn)
        main_layout.addLayout(action_bar)

        # Signal connections
        self.add_files_btn.clicked.connect(self._on_add_files)
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        self.clear_btn.clicked.connect(self._clear_list)
        self.convert_all_btn.clicked.connect(self._start_batch_conversion)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for u in event.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS:
                paths.append(p)
            elif p.is_dir():
                paths.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTS])

        self._add_paths_to_table(paths)

    def _on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "選取要轉檔的多媒體檔案",
            "",
            "影音檔案 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus *.mp4 *.mkv *.webm *.mov);;所有檔案 (*.*)"
        )
        if files:
            paths = [Path(f) for f in files]
            self._add_paths_to_table(paths)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "選取資料夾")
        if folder:
            p = Path(folder)
            paths = [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTS]
            self._add_paths_to_table(paths)

    def _add_paths_to_table(self, paths: List[Path]):
        new_paths = [p for p in paths if p not in self.file_items]
        if not new_paths:
            return

        start_row = len(self.file_items)
        for p in new_paths:
            self.file_items.append(p)
            row = self.table.rowCount()
            self.table.insertRow(row)
            size_str = format_bytes(p.stat().st_size)

            self.table.setItem(row, 0, QTableWidgetItem(p.name))
            self.table.setItem(row, 1, QTableWidgetItem("解析中..."))
            self.table.setItem(row, 2, QTableWidgetItem("--"))
            self.table.setItem(row, 3, QTableWidgetItem("--"))
            self.table.setItem(row, 4, QTableWidgetItem("--"))
            self.table.setItem(row, 5, QTableWidgetItem(size_str))
            self.table.setItem(row, 6, QTableWidgetItem("待處理"))

        self._update_visibility()

        # Non-blocking probe worker
        self._probe_worker = ProbeWorker(self.ffmpeg_engine, new_paths, start_row)
        self._probe_worker.item_probed.connect(self._on_item_probed)
        self._probe_worker.start()

    def _on_item_probed(self, row: int, path: Path, info: Optional[MediaInfo]):
        if row < self.table.rowCount() and info:
            self.media_infos[str(path)] = info
            codec_str = "--"
            sr_str = "--"
            ch_str = "--"
            dur_str = format_time(info.duration)

            if info.audio_stream:
                codec_str = info.audio_stream.codec_name
                sr_str = f"{info.audio_stream.sample_rate} Hz"
                ch_str = f"{info.audio_stream.channels} ch"
            elif info.video_stream:
                codec_str = f"Video: {info.video_stream.codec_name}"

            self.table.setItem(row, 1, QTableWidgetItem(codec_str))
            self.table.setItem(row, 2, QTableWidgetItem(sr_str))
            self.table.setItem(row, 3, QTableWidgetItem(ch_str))
            self.table.setItem(row, 4, QTableWidgetItem(dur_str))
        elif row < self.table.rowCount():
            self.table.setItem(row, 1, QTableWidgetItem("無法讀取"))

    def _clear_list(self):
        self.file_items.clear()
        self.media_infos.clear()
        self.table.setRowCount(0)
        self._update_visibility()

    def _update_visibility(self):
        has_items = len(self.file_items) > 0
        self.table.setVisible(has_items)
        self.empty_state.setVisible(not has_items)

    def closeEvent(self, event):
        if hasattr(self, "_probe_worker") and self._probe_worker and self._probe_worker.isRunning():
            self._probe_worker.quit()
            self._probe_worker.wait(500)
        super().closeEvent(event)

    def _start_batch_conversion(self):
        if not self.file_items:
            ToastManager.show_toast(self, "清單為空", "請先加入至少一個要轉檔的檔案！", ToastType.WARNING)
            return

        cfg = self.config_mgr.get()
        out_dir = cfg.output_dir

        target_choice = self.batch_fmt_combo.currentText()
        is_mmd = "MMD" in target_choice

        if is_mmd:
            mode = "mmd_wav"
            fmt = "WAV"
            q = "best"
        elif "MP3 (320" in target_choice:
            mode = "audio"
            fmt = "MP3"
            q = "320k"
        elif "MP3 (192" in target_choice:
            mode = "audio"
            fmt = "MP3"
            q = "192k"
        elif "FLAC" in target_choice:
            mode = "audio"
            fmt = "FLAC"
            q = "best"
        elif "M4A" in target_choice:
            mode = "audio"
            fmt = "M4A"
            q = "best"
        elif "OGG" in target_choice:
            mode = "audio"
            fmt = "OGG"
            q = "best"
        elif "OPUS" in target_choice:
            mode = "audio"
            fmt = "OPUS"
            q = "best"
        elif "MP4" in target_choice:
            mode = "video"
            fmt = "MP4"
            q = "best"
        else:
            mode = "audio"
            fmt = "WAV"
            q = "best"

        for row, path in enumerate(self.file_items):
            self.table.setItem(row, 6, QTableWidgetItem("已排入佇列"))
            self.task_manager.add_convert_task(
                input_file=path,
                output_dir=out_dir,
                mode=mode,
                target_format=fmt,
                audio_quality=q,
                sample_rate=cfg.mmd_wav.sample_rate,
                channels=cfg.mmd_wav.channels,
                volume_gain_db=cfg.mmd_wav.volume_gain_db
            )

        ToastManager.show_toast(
            self,
            title="批次轉檔已啟動",
            message=f"已成功將 {len(self.file_items)} 個檔案排入轉檔佇列！",
            toast_type=ToastType.SUCCESS
        )
