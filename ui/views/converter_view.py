"""
Batch Local Media Converter View for MMD Audio Downloader.
Features modern Windows 11 Fluent Design matching reference 03_converter_view.png:
Hero banner with target format selector, dashed cyan drop zone with feature pills,
rich media file table, and unified batch execution bar.
"""

from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
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
from ui.components.hero_banner import HeroBannerWidget
from ui.components.toast import ToastManager, ToastType
from ui.theme import ThemeManager, adjust_color, get_contrast_text_color, hex_to_rgb


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


class DropZoneWidget(QFrame):
    """Interactive drop zone card with cyan dashed border and feature pills."""

    add_files_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._is_hovered = False
        self._setup_ui()
        ThemeManager().theme_changed.connect(lambda *_: self.update())

    def _setup_ui(self):
        self.setFixedHeight(240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Center glowing icon
        icon_lbl = QLabel("📁")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 40px; background: transparent;")
        layout.addWidget(icon_lbl)

        # Title
        self.title_lbl = QLabel("拖曳音樂或影片檔案至此處，或使用下方按鈕")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF; background: transparent;")
        layout.addWidget(self.title_lbl)

        # Subtitle
        self.sub_lbl = QLabel("支援 MP3、MP4、FLAC、M4A、OGG、WAV、MKV 等格式，可同時加入多個檔案")
        self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_lbl.setStyleSheet("font-size: 12px; color: #8E95A5; background: transparent;")
        layout.addWidget(self.sub_lbl)

        # 3 Feature Pills
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(10)
        pills_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for text in ["🎴 多檔批次轉換", "⚡ 快速高效處理", "✓ 保留高音質"]:
            pill = QLabel(text)
            pill.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 210, 180, 0.12);
                    color: #00D2B4;
                    border: 1px solid rgba(0, 210, 180, 0.35);
                    border-radius: 10px;
                    padding: 3px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
            pills_layout.addWidget(pill)

        layout.addLayout(pills_layout)
        layout.addSpacing(4)

        # Browse Button
        self.browse_btn = QPushButton("📁  瀏覽並加入檔案...")
        self.browse_btn.setFixedHeight(36)
        self.browse_btn.setMinimumWidth(180)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E222B;
                color: #FFFFFF;
                border: 1px solid #363D4E;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 0px 20px;
            }
            QPushButton:hover {
                background-color: #272C38;
                border: 1px solid #00D2B4;
                color: #00D2B4;
            }
        """)
        self.browse_btn.clicked.connect(self.add_files_clicked.emit)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.add_files_clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        radius = 12

        tm = ThemeManager()
        dark = tm.is_dark()
        accent = tm.accent_color
        r, g, b = hex_to_rgb(accent)

        bg_col = QColor(20, 24, 31) if dark else QColor(248, 250, 252)
        border_col = QColor(r, g, b, 130 if self._is_hovered else 80)

        path = QPainterPath()
        path.addRoundedRect(1, 1, w - 2, h - 2, radius, radius)
        painter.fillPath(path, bg_col)

        pen = QPen(border_col, 1.6, Qt.PenStyle.DashLine)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()


class ConverterView(QWidget):
    """View for converting local audio and video files in batch matching 03_converter_view.png."""

    SUPPORTED_EXTS = {
        ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus",
        ".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".ts"
    }

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.ffmpeg_engine = self.task_manager.ffmpeg_engine
        self.theme_mgr = ThemeManager()

        self.file_items: List[Path] = []
        self.media_infos: Dict[str, MediaInfo] = {}

        self._setup_ui()
        self.setAcceptDrops(True)
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # Target Format dropdown aligned on the right of header
        fmt_container = QWidget()
        fmt_layout = QHBoxLayout(fmt_container)
        fmt_layout.setContentsMargins(0, 0, 0, 0)
        fmt_layout.setSpacing(8)

        lbl_target = QLabel("統一目標格式：")
        lbl_target.setStyleSheet("font-size: 13px; font-weight: 500; color: #CAD1DC; background: transparent;")
        self.batch_fmt_combo = QComboBox()
        self.batch_fmt_combo.setFixedHeight(34)
        self.batch_fmt_combo.setMinimumWidth(260)
        self.batch_fmt_combo.addItems([
            "★ MMD 專用 WAV (44.1 kHz / 16-bit)",
            "WAV (標準 44.1 kHz PCM)",
            "MP3 (最高音質 320 kbps)",
            "MP3 (標準音質 192 kbps)",
            "FLAC (無損壓縮)",
            "M4A (AAC 256 kbps)",
            "MP4 (H.264 影片容器)",
            "MKV (多軌影音容器)"
        ])
        fmt_layout.addWidget(lbl_target)
        fmt_layout.addWidget(self.batch_fmt_combo)

        # 1. Page Header matching 03_converter_view.png
        self.hero_banner = HeroBannerWidget(
            title="⇄  格式轉換",
            desc=[
                "支援多種影音格式相互轉換，提供單檔與多檔批次處理能力。"
            ],
            badge_type="converter",
            right_widget=fmt_container
        )
        main_layout.addWidget(self.hero_banner)

        # 2. Drop Zone (shown when table is empty)
        self.drop_zone = DropZoneWidget(self)
        self.drop_zone.add_files_clicked.connect(self._on_add_files)
        main_layout.addWidget(self.drop_zone)

        # 3. File List Table (shown when files are added)
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
        self.table.setVisible(False)
        main_layout.addWidget(self.table, 1)

        main_layout.addStretch(1)

        # 4. Bottom Action Bar matching 03_converter_view.png
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.add_files_btn = QPushButton("📁 加入檔案...")
        self.add_files_btn.setFixedHeight(36)
        self.add_folder_btn = QPushButton("📁 加入資料夾...")
        self.add_folder_btn.setFixedHeight(36)
        self.clear_btn = QPushButton("🗑 清空清單")
        self.clear_btn.setFixedHeight(36)

        self.convert_all_btn = QPushButton("▶ 開始全部批次轉換")
        self.convert_all_btn.setFixedHeight(38)
        self.convert_all_btn.setMinimumWidth(180)
        self.convert_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D2B4;
                color: #0E151B;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 0px 20px;
            }
            QPushButton:hover {
                background-color: #1AE0C4;
            }
            QPushButton:pressed {
                background-color: #00BFA3;
            }
        """)

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
        folder = QFileDialog.getExistingDirectory(self, "選取包含媒體的資料夾")
        if folder:
            p = Path(folder)
            paths = [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTS]
            self._add_paths_to_table(paths)

    def _add_paths_to_table(self, paths: List[Path]):
        new_paths = [p for p in paths if p not in self.file_items]
        if not new_paths:
            return

        start_row = len(self.file_items)
        self.file_items.extend(new_paths)

        self.table.setRowCount(len(self.file_items))
        for idx, p in enumerate(new_paths):
            row = start_row + idx
            name_item = QTableWidgetItem(p.name)
            name_item.setToolTip(str(p))
            self.table.setItem(row, 0, name_item)

            ext_item = QTableWidgetItem(p.suffix.upper().lstrip("."))
            ext_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, ext_item)

            sr_item = QTableWidgetItem("讀取中...")
            sr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, sr_item)

            ch_item = QTableWidgetItem("--")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, ch_item)

            dur_item = QTableWidgetItem("--:--")
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, dur_item)

            try:
                sz = format_bytes(p.stat().st_size)
            except Exception:
                sz = "--"
            sz_item = QTableWidgetItem(sz)
            sz_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, sz_item)

            status_item = QTableWidgetItem("就緒")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, status_item)

        self.drop_zone.setVisible(False)
        self.table.setVisible(True)

        # Launch background probe
        self._probe_worker = ProbeWorker(self.ffmpeg_engine, new_paths, start_row)
        self._probe_worker.item_probed.connect(self._on_item_probed)
        self._probe_worker.start()

    def _on_item_probed(self, row: int, p: Path, info: Optional[MediaInfo]):
        if not info:
            return
        self.media_infos[str(p)] = info

        # 1. Format/Codec
        codec_name = "--"
        if info.audio_stream:
            codec_name = info.audio_stream.codec_name.upper()
        elif info.video_stream:
            codec_name = f"{info.video_stream.codec_name.upper()} 影片"

        ext_item = self.table.item(row, 1)
        if ext_item:
            ext_item.setText(f"{p.suffix.upper().lstrip('.')} ({codec_name})")

        # 2. Sample rate
        if info.audio_stream and info.audio_stream.sample_rate:
            sr_item = self.table.item(row, 2)
            if sr_item:
                sr_item.setText(f"{info.audio_stream.sample_rate:,} Hz")

        # 3. Channels
        if info.audio_stream and info.audio_stream.channels:
            ch_item = self.table.item(row, 3)
            if ch_item:
                ch = info.audio_stream.channels
                ch_item.setText(f"{ch} 聲道 ({'立體' if ch == 2 else '單聲'})")

        # 4. Duration
        dur_item = self.table.item(row, 4)
        if dur_item:
            dur_item.setText(info.display_duration)

    def _clear_list(self):
        self.file_items.clear()
        self.media_infos.clear()
        self.table.setRowCount(0)
        self.table.setVisible(False)
        self.drop_zone.setVisible(True)

    def _start_batch_conversion(self):
        if not self.file_items:
            QMessageBox.information(self, "清單為空", "請先加入至少一個要轉檔的音訊或影片檔案！")
            return

        cfg = self.config_mgr.get()
        out_dir = cfg.output_dir
        combo_text = self.batch_fmt_combo.currentText()

        # Parse target format
        mode = "audio"
        fmt = "WAV"
        sr = 44100
        ch = 2
        quality = "best"

        if "MMD 專用" in combo_text:
            mode = "mmd_wav"
            fmt = "WAV"
            sr = 44100
            ch = 2
        elif "WAV" in combo_text:
            fmt = "WAV"
            sr = 44100
        elif "MP3" in combo_text:
            fmt = "MP3"
            quality = "320k" if "320" in combo_text else "192k"
        elif "FLAC" in combo_text:
            fmt = "FLAC"
        elif "M4A" in combo_text:
            fmt = "M4A"
            quality = "256k"
        elif "MP4" in combo_text:
            mode = "video"
            fmt = "MP4"
        elif "MKV" in combo_text:
            mode = "video"
            fmt = "MKV"

        for p in self.file_items:
            self.task_manager.add_conversion_task(
                input_file=p,
                output_dir=out_dir,
                mode=mode,
                target_format=fmt,
                audio_quality=quality,
                sample_rate=sr,
                channels=ch
            )

        ToastManager.show_toast(
            self,
            title="批次轉檔已加入任務佇列",
            message=f"已將 {len(self.file_items)} 個檔案排入轉檔程序，請至「任務管理」查看進度",
            toast_type=ToastType.SUCCESS
        )

    def _on_theme_changed(self, mode: str, accent: str):
        pass
