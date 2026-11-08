"""
Multi-Platform Media Downloader View for MMD Audio Downloader.
Features modern Windows 11 Fluent Design matching the reference specification:
compact URL bar with paste button, horizontal thumbnail preview with duration badge,
single-row 5-format cards, 2-row compact parameter settings, full-width download button,
and integrated real-time active task progress bar.
"""

import re
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.downloader_engine import DownloaderEngine, ParsedMediaItem
from core.task_manager import TaskItem, TaskManager, TaskStatus
from core.utils import format_bytes, format_speed, format_time, parse_time_to_seconds
from ui.components.format_card_selector import FormatCardSelector
from ui.components.thumbnail_widget import ThumbnailWidget
from ui.components.toast import ToastManager, ToastType
from ui.theme import ThemeManager, get_contrast_text_color, hex_to_rgb


class ParseWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, downloader: DownloaderEngine, url: str):
        super().__init__()
        self.downloader = downloader
        self.url = url

    def run(self):
        try:
            items = self.downloader.parse_url(self.url)
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))


class DownloadView(QWidget):
    """View for parsing and downloading media from online platforms."""

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.downloader = self.task_manager.downloader_engine
        self.current_parsed_items: List[ParsedMediaItem] = []
        self._parse_thread: Optional[ParseWorker] = None
        self._active_task_id: Optional[str] = None

        self._setup_ui()
        self._restore_preferences()
        self._connect_task_signals()
        ThemeManager().theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed("dark" if ThemeManager().is_dark() else "light", ThemeManager().accent_color)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. Page Title Header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        self.view_title = QLabel("↓ 影音下載")
        self.view_title.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent; color: #F2F3F5;")
        title_row.addWidget(self.view_title)
        title_row.addStretch(1)

        self.batch_toggle_btn = QPushButton("切換多網址批次輸入")
        self.batch_toggle_btn.setFixedHeight(28)
        self.batch_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E212A;
                color: #A6ACB8;
                border: 1px solid #2B2F3B;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #272B37;
                color: #FFFFFF;
                border: 1px solid #3C4252;
            }
        """)
        title_row.addWidget(self.batch_toggle_btn)
        header_layout.addLayout(title_row)

        self.view_subtitle = QLabel("支援 YouTube、Bilibili、Niconico 等影音平台，解析並下載為 WAV、MP3、MP4、FLAC、M4A 等格式。")
        self.view_subtitle.setStyleSheet("color: #8E95A5; font-size: 12px; background: transparent;")
        header_layout.addWidget(self.view_subtitle)
        layout.addWidget(header_widget)

        # 2. URL Input Bar (Single Line with Paste and Parse buttons)
        input_bar_layout = QHBoxLayout()
        input_bar_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=XXXXXXXXXXX")
        self.url_input.setMinimumHeight(38)
        self.url_input.textChanged.connect(self._on_url_text_changed)
        self.url_input.returnPressed.connect(self._start_parse)

        self.paste_btn = QPushButton("📋 貼上")
        self.paste_btn.setMinimumHeight(38)
        self.paste_btn.setMinimumWidth(80)
        self.paste_btn.clicked.connect(self._paste_clipboard)

        self.parse_btn = QPushButton("🔍 解析資訊")
        self.parse_btn.setProperty("class", "primary")
        self.parse_btn.setMinimumHeight(38)
        self.parse_btn.setMinimumWidth(110)
        self.parse_btn.clicked.connect(self._start_parse)

        input_bar_layout.addWidget(self.url_input, 1)
        input_bar_layout.addWidget(self.paste_btn)
        input_bar_layout.addWidget(self.parse_btn)
        layout.addLayout(input_bar_layout)

        # Multi-line batch URLs edit (hidden by default)
        self.batch_url_edit = QPlainTextEdit()
        self.batch_url_edit.setPlaceholderText("每行一個網址，可一次貼上多個影音網址進行批次下載...\nhttps://...\nhttps://...")
        self.batch_url_edit.setMaximumHeight(90)
        self.batch_url_edit.setVisible(False)
        layout.addWidget(self.batch_url_edit)

        # 3. Parsed Media Preview Card (Horizontal layout matching reference mockup)
        self.preview_card = QFrame()
        self.preview_card.setProperty("class", "card")
        self.preview_card.setFixedHeight(114)
        self.preview_card.setVisible(False)
        preview_layout = QHBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(10, 8, 12, 8)
        preview_layout.setSpacing(12)

        # Left 16:9 Thumbnail (160x90) with duration badge
        self.thumb_widget = ThumbnailWidget(width=160, height=90, parent=self.preview_card)
        preview_layout.addWidget(self.thumb_widget)

        # Right Info Column
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.preview_title = QLabel("影片標題")
        self.preview_title.setStyleSheet("font-size: 15px; font-weight: bold; background: transparent; padding: 0px;")
        self.preview_title.setFixedHeight(26)
        self.preview_title.setWordWrap(False)

        meta_badge_row = QHBoxLayout()
        meta_badge_row.setSpacing(8)

        self.preview_platform_tag = QLabel("▶ YouTube")
        self.preview_platform_tag.setStyleSheet(
            "background-color: rgba(255, 68, 68, 0.2); color: #FF5252; "
            "border-radius: 4px; padding: 2px 7px; font-weight: bold; font-size: 11px; background: transparent;"
        )
        self.preview_platform_tag.setFixedHeight(20)
        meta_badge_row.addWidget(self.preview_platform_tag)
        meta_badge_row.addStretch(1)

        self.preview_meta = QLabel("時長：-- | 解析品質：-- | 來源：--")
        self.preview_meta.setStyleSheet("color: #A3AAB8; font-size: 12px; background: transparent; padding: 0px;")
        self.preview_meta.setFixedHeight(20)

        info_layout.addWidget(self.preview_title)
        info_layout.addLayout(meta_badge_row)
        info_layout.addWidget(self.preview_meta)
        preview_layout.addLayout(info_layout, 1)

        layout.addWidget(self.preview_card)

        # 4. Format Card Selector (Horizontal row of 5 cards)
        self.format_selector = FormatCardSelector(default_format="WAV", parent=self)
        self.format_selector.format_changed.connect(self._on_format_changed)
        layout.addWidget(self.format_selector)

        # 5. Dynamic Parameter Box (Switches according to selected format)
        self.param_stack = QStackedWidget()
        self.param_stack.setFixedHeight(154)

        self.page_wav = self._create_wav_param_page()
        self.param_stack.addWidget(self.page_wav)  # Index 0: WAV

        self.page_mp3 = self._create_mp3_param_page()
        self.param_stack.addWidget(self.page_mp3)  # Index 1: MP3

        self.page_mp4 = self._create_mp4_param_page()
        self.param_stack.addWidget(self.page_mp4)  # Index 2: MP4

        self.page_flac = self._create_flac_param_page()
        self.param_stack.addWidget(self.page_flac) # Index 3: FLAC

        self.page_m4a = self._create_m4a_param_page()
        self.param_stack.addWidget(self.page_m4a)  # Index 4: M4A

        layout.addWidget(self.param_stack)

        # 6. Full-Width Primary Action Button: "↓ 下載 WAV"
        self.download_btn = QPushButton("↓ 下載 WAV")
        self.download_btn.setProperty("class", "primary")
        self.download_btn.setMinimumHeight(42)
        self.download_btn.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.download_btn.clicked.connect(self._start_download)
        layout.addWidget(self.download_btn)

        # 7. Bottom Active Task Section (Real-time progress row matching reference mockup)
        self.task_section = QWidget()
        task_sec_layout = QVBoxLayout(self.task_section)
        task_sec_layout.setContentsMargins(0, 4, 0, 0)
        task_sec_layout.setSpacing(6)

        self.task_sec_title = QLabel("下載任務 (0)")
        self.task_sec_title.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        task_sec_layout.addWidget(self.task_sec_title)

        # Active Task Card
        self.active_task_card = QFrame()
        self.active_task_card.setProperty("class", "card")
        self.active_task_card.setFixedHeight(74)
        active_layout = QHBoxLayout(self.active_task_card)
        active_layout.setContentsMargins(12, 8, 14, 8)
        active_layout.setSpacing(12)

        # Left mini thumb or icon
        self.active_thumb = QLabel("🎬")
        self.active_thumb.setFixedSize(54, 40)
        self.active_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_thumb.setStyleSheet("background-color: #242832; border-radius: 6px; font-size: 20px;")
        active_layout.addWidget(self.active_thumb)

        # Middle info
        middle_info = QVBoxLayout()
        middle_info.setContentsMargins(0, 2, 0, 2)
        middle_info.setSpacing(2)
        middle_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.active_title_lbl = QLabel("等候任務中...")
        self.active_title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent; padding: 0px;")
        self.active_title_lbl.setFixedHeight(22)
        self.active_title_lbl.setWordWrap(False)

        self.active_sub_lbl = QLabel("WAV (PCM 16-bit / 44.1 kHz / Stereo)")
        self.active_sub_lbl.setStyleSheet("color: #A3AAB8; font-size: 11px; background: transparent; padding: 0px;")
        self.active_sub_lbl.setFixedHeight(18)

        middle_info.addWidget(self.active_title_lbl)
        middle_info.addWidget(self.active_sub_lbl)
        active_layout.addLayout(middle_info, 1)

        # Right progress stats & controls
        self.active_right_container = QWidget()
        self.active_right_container.setFixedHeight(50)
        right_v = QVBoxLayout(self.active_right_container)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(2)

        stats_top = QHBoxLayout()
        stats_top.setContentsMargins(0, 0, 0, 0)
        self.active_bytes_lbl = QLabel("0.0 MB / 0.0 MB")
        self.active_bytes_lbl.setStyleSheet("color: #A3AAB8; font-size: 11px; background: transparent; padding: 0px;")
        self.active_bytes_lbl.setFixedHeight(18)
        self.active_pct_lbl = QLabel("0%")
        self.active_pct_lbl.setStyleSheet("color: #F2F3F5; font-weight: bold; font-size: 11px; background: transparent; padding: 0px;")
        self.active_pct_lbl.setFixedHeight(18)
        stats_top.addWidget(self.active_bytes_lbl)
        stats_top.addStretch(1)
        stats_top.addWidget(self.active_pct_lbl)
        right_v.addLayout(stats_top)

        # Sleek Thin Progress Bar
        self.active_progress_bar = QProgressBar()
        self.active_progress_bar.setRange(0, 100)
        self.active_progress_bar.setValue(0)
        self.active_progress_bar.setFixedHeight(6)
        right_v.addWidget(self.active_progress_bar)

        self.active_speed_eta_lbl = QLabel("↓ 0.0 KB/s | 剩餘時間：--")
        self.active_speed_eta_lbl.setStyleSheet("color: #A3AAB8; font-size: 11px; background: transparent; padding: 0px;")
        self.active_speed_eta_lbl.setFixedHeight(18)
        right_v.addWidget(self.active_speed_eta_lbl)

        active_layout.addWidget(self.active_right_container, 1)

        # Action Buttons (Pause & Cancel)
        action_btn_layout = QHBoxLayout()
        action_btn_layout.setSpacing(6)
        action_btn_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.active_pause_btn = QPushButton("⏸")
        self.active_pause_btn.setFixedSize(32, 32)
        self.active_pause_btn.setToolTip("暫停 / 繼續")
        self.active_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #212530;
                color: #FFFFFF;
                border: 1px solid #323846;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2D3342;
                color: #FFFFFF;
                border: 1px solid #454D60;
            }
        """)

        self.active_cancel_btn = QPushButton("✕")
        self.active_cancel_btn.setFixedSize(32, 32)
        self.active_cancel_btn.setToolTip("取消任務")
        self.active_cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #212530;
                color: #FFFFFF;
                border: 1px solid #323846;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #38242A;
                color: #FF5252;
                border: 1px solid #662B35;
            }
        """)
        self.active_cancel_btn.clicked.connect(self._cancel_active_task)

        action_btn_layout.addWidget(self.active_pause_btn)
        action_btn_layout.addWidget(self.active_cancel_btn)
        active_layout.addLayout(action_btn_layout)

        task_sec_layout.addWidget(self.active_task_card)
        self.task_section.setVisible(False)
        layout.addWidget(self.task_section)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        self.batch_toggle_btn.clicked.connect(self._toggle_batch_mode)

    # ---------------- Parameter Pages ----------------
    def _create_wav_param_page(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel("WAV 輸出設定 (MMD 最佳相容建議)")
        title.setFixedHeight(28)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00D2B4; background: transparent;")
        v.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card.setFixedHeight(116)
        grid = QGridLayout(card)
        grid.setSpacing(10)
        grid.setContentsMargins(14, 10, 14, 10)

        # Row 1: Sample Rate, Bit Depth, Channels
        lbl_sr = QLabel("採樣頻率")
        lbl_sr.setFixedWidth(66)
        lbl_sr.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_sr, 0, 0)
        self.wav_sr_combo = QComboBox()
        self.wav_sr_combo.addItems(["44,100 Hz (MMD 標準音質)", "48,000 Hz"])
        grid.addWidget(self.wav_sr_combo, 0, 1)

        lbl_bit = QLabel("位元深度")
        lbl_bit.setFixedWidth(66)
        lbl_bit.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_bit, 0, 2)
        self.wav_bit_lbl = QComboBox()
        self.wav_bit_lbl.addItems(["16-bit Signed PCM (建議)"])
        self.wav_bit_lbl.setStyleSheet("color: #00D2B4; font-weight: bold;")
        grid.addWidget(self.wav_bit_lbl, 0, 3)

        lbl_ch = QLabel("聲道配置")
        lbl_ch.setFixedWidth(66)
        lbl_ch.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_ch, 0, 4)
        self.wav_ch_combo = QComboBox()
        self.wav_ch_combo.addItems(["Stereo 雙聲道 (MMD 預設)", "Mono 單聲道"])
        grid.addWidget(self.wav_ch_combo, 0, 5)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(5, 1)

        # Row 2: Save directory
        lbl_save = QLabel("儲存位置")
        lbl_save.setFixedWidth(66)
        lbl_save.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_save, 1, 0)
        save_box = QHBoxLayout()
        save_box.setSpacing(8)
        self.wav_save_input = QLineEdit(self.config_mgr.get().output_dir)
        self.wav_save_input.setReadOnly(True)
        self.wav_browse_btn = QPushButton("📁 瀏覽...")
        self.wav_browse_btn.setFixedWidth(90)
        self.wav_browse_btn.clicked.connect(self._browse_save_directory)
        save_box.addWidget(self.wav_save_input, 1)
        save_box.addWidget(self.wav_browse_btn)
        grid.addLayout(save_box, 1, 1, 1, 5)

        v.addWidget(card)
        return container

    def _create_mp3_param_page(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel("MP3 輸出音質設定")
        title.setFixedHeight(28)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00D2B4; background: transparent;")
        v.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card.setFixedHeight(116)
        grid = QGridLayout(card)
        grid.setSpacing(10)
        grid.setContentsMargins(14, 10, 14, 10)

        lbl_q = QLabel("位元率品質")
        lbl_q.setFixedWidth(72)
        lbl_q.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_q, 0, 0)
        self.mp3_quality_combo = QComboBox()
        self.mp3_quality_combo.addItems([
            "320 kbps (最高品質 · 推薦)",
            "256 kbps (極佳品質)",
            "192 kbps (標準音質)",
            "128 kbps (省空間容量)"
        ])
        grid.addWidget(self.mp3_quality_combo, 0, 1)

        info = QLabel("使用 LAME 高品質立體聲編碼")
        info.setStyleSheet("color: #8E95A5; font-size: 12px; background: transparent;")
        grid.addWidget(info, 0, 2)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        # Save directory
        lbl_save = QLabel("儲存位置")
        lbl_save.setFixedWidth(72)
        lbl_save.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_save, 1, 0)
        save_box = QHBoxLayout()
        save_box.setSpacing(8)
        self.mp3_save_input = QLineEdit(self.config_mgr.get().output_dir)
        self.mp3_save_input.setReadOnly(True)
        self.mp3_browse_btn = QPushButton("📁 瀏覽...")
        self.mp3_browse_btn.setFixedWidth(90)
        self.mp3_browse_btn.clicked.connect(self._browse_save_directory)
        save_box.addWidget(self.mp3_save_input, 1)
        save_box.addWidget(self.mp3_browse_btn)
        grid.addLayout(save_box, 1, 1, 1, 2)

        v.addWidget(card)
        return container

    def _create_mp4_param_page(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel("MP4 影片輸出設定 (完整影像與音訊)")
        title.setFixedHeight(28)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00D2B4; background: transparent;")
        v.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card.setFixedHeight(116)
        grid = QGridLayout(card)
        grid.setSpacing(10)
        grid.setContentsMargins(14, 10, 14, 10)

        lbl_res = QLabel("影片解析度")
        lbl_res.setFixedWidth(72)
        lbl_res.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_res, 0, 0)
        self.mp4_res_combo = QComboBox()
        self.mp4_res_combo.addItems([
            "最佳可用畫質 (自動最高)",
            "2160p (4K UHD)",
            "1440p (2K QHD)",
            "1080p (Full HD)",
            "720p (HD)",
            "480p (SD)",
            "360p"
        ])
        grid.addWidget(self.mp4_res_combo, 0, 1)

        lbl_enc = QLabel("影音編碼")
        lbl_enc.setFixedWidth(66)
        lbl_enc.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_enc, 0, 2)
        self.mp4_compat_label = QLabel("H.264 (AVC) + AAC (100% 相容)")
        self.mp4_compat_label.setStyleSheet("color: #00D2B4; font-weight: bold; background: transparent;")
        grid.addWidget(self.mp4_compat_label, 0, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        # Save directory
        lbl_save = QLabel("儲存位置")
        lbl_save.setFixedWidth(72)
        lbl_save.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_save, 1, 0)
        save_box = QHBoxLayout()
        save_box.setSpacing(8)
        self.mp4_save_input = QLineEdit(self.config_mgr.get().output_dir)
        self.mp4_save_input.setReadOnly(True)
        self.mp4_browse_btn = QPushButton("📁 瀏覽...")
        self.mp4_browse_btn.setFixedWidth(90)
        self.mp4_browse_btn.clicked.connect(self._browse_save_directory)
        save_box.addWidget(self.mp4_save_input, 1)
        save_box.addWidget(self.mp4_browse_btn)
        grid.addLayout(save_box, 1, 1, 1, 3)

        v.addWidget(card)
        return container

    def _create_flac_param_page(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel("FLAC 無損音訊設定")
        title.setFixedHeight(28)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00D2B4; background: transparent;")
        v.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card.setFixedHeight(116)
        grid = QGridLayout(card)
        grid.setSpacing(10)
        grid.setContentsMargins(14, 10, 14, 10)

        lbl_lvl = QLabel("壓縮層級")
        lbl_lvl.setFixedWidth(66)
        lbl_lvl.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_lvl, 0, 0)
        self.flac_level_combo = QComboBox()
        self.flac_level_combo.addItems(["層級 5 (標準平衡)", "層級 8 (最大壓縮)", "層級 0 (最快編碼)"])
        grid.addWidget(self.flac_level_combo, 0, 1)

        notice = QLabel("無損壓縮 · 完整保留動態")
        notice.setStyleSheet("color: #8E95A5; font-size: 12px; background: transparent;")
        grid.addWidget(notice, 0, 2)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        # Save directory
        lbl_save = QLabel("儲存位置")
        lbl_save.setFixedWidth(66)
        lbl_save.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_save, 1, 0)
        save_box = QHBoxLayout()
        save_box.setSpacing(8)
        self.flac_save_input = QLineEdit(self.config_mgr.get().output_dir)
        self.flac_save_input.setReadOnly(True)
        self.flac_browse_btn = QPushButton("📁 瀏覽...")
        self.flac_browse_btn.setFixedWidth(90)
        self.flac_browse_btn.clicked.connect(self._browse_save_directory)
        save_box.addWidget(self.flac_save_input, 1)
        save_box.addWidget(self.flac_browse_btn)
        grid.addLayout(save_box, 1, 1, 1, 2)

        v.addWidget(card)
        return container

    def _create_m4a_param_page(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel("M4A 輸出音質設定")
        title.setFixedHeight(28)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00D2B4; background: transparent;")
        v.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        card.setFixedHeight(116)
        grid = QGridLayout(card)
        grid.setSpacing(10)
        grid.setContentsMargins(14, 10, 14, 10)

        lbl_aac = QLabel("AAC 位元率")
        lbl_aac.setFixedWidth(72)
        lbl_aac.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_aac, 0, 0)
        self.m4a_quality_combo = QComboBox()
        self.m4a_quality_combo.addItems(["256 kbps (iTunes 最佳音質)", "320 kbps (最高)", "192 kbps (標準)"])
        grid.addWidget(self.m4a_quality_combo, 0, 1)

        notice = QLabel("蘋果裝置相容首選 · 省容量")
        notice.setStyleSheet("color: #8E95A5; font-size: 12px; background: transparent;")
        grid.addWidget(notice, 0, 2)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        # Save directory
        lbl_save = QLabel("儲存位置")
        lbl_save.setFixedWidth(72)
        lbl_save.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        grid.addWidget(lbl_save, 1, 0)
        save_box = QHBoxLayout()
        save_box.setSpacing(8)
        self.m4a_save_input = QLineEdit(self.config_mgr.get().output_dir)
        self.m4a_save_input.setReadOnly(True)
        self.m4a_browse_btn = QPushButton("📁 瀏覽...")
        self.m4a_browse_btn.setFixedWidth(90)
        self.m4a_browse_btn.clicked.connect(self._browse_save_directory)
        save_box.addWidget(self.m4a_save_input, 1)
        save_box.addWidget(self.m4a_browse_btn)
        grid.addLayout(save_box, 1, 1, 1, 2)

        v.addWidget(card)
        return container

        v.addWidget(card)
        return container

        v.addWidget(card)
        return container

    def _browse_save_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "選取儲存資料夾", self.config_mgr.get().output_dir)
        if folder:
            cfg = self.config_mgr.get()
            cfg.output_dir = folder
            self.config_mgr.save(cfg)
            for inp in [
                getattr(self, "wav_save_input", None),
                getattr(self, "mp3_save_input", None),
                getattr(self, "mp4_save_input", None),
                getattr(self, "flac_save_input", None),
                getattr(self, "m4a_save_input", None)
            ]:
                if inp:
                    inp.setText(folder)

    def _paste_clipboard(self):
        clip_text = QApplication.clipboard().text().strip()
        if clip_text:
            if self.batch_url_edit.isVisible():
                self.batch_url_edit.setPlainText(clip_text)
            else:
                self.url_input.setText(clip_text)

    def _on_format_changed(self, fmt_key: str):
        mapping = {
            "WAV": 0,
            "MP3": 1,
            "MP4": 2,
            "FLAC": 3,
            "M4A": 4,
        }
        idx = mapping.get(fmt_key.upper(), 0)
        self.param_stack.setCurrentIndex(idx)
        self.download_btn.setText(f"↓ 下載 {fmt_key.upper()}")

        cfg = self.config_mgr.get()
        cfg.preferred_format = fmt_key.upper()
        self.config_mgr.save(cfg)

    def _restore_preferences(self):
        cfg = self.config_mgr.get()
        pref = getattr(cfg, "preferred_format", "WAV") or "WAV"
        self.format_selector.set_format(pref)
        self._on_format_changed(pref)

    def _on_url_text_changed(self, text: str):
        if not text.strip():
            self.preview_card.setVisible(False)
            self.thumb_widget.clear()

    def _toggle_batch_mode(self):
        is_batch = not self.batch_url_edit.isVisible()
        self.batch_url_edit.setVisible(is_batch)
        self.url_input.setVisible(not is_batch)
        self.batch_toggle_btn.setText("切換單網址輸入" if is_batch else "切換多網址批次輸入")

    def _start_parse(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "輸入錯誤", "請先輸入有效的影音網址！")
            return

        self.parse_btn.setEnabled(False)
        self.parse_btn.setText("解析中...")
        self.thumb_widget.clear()

        self._parse_thread = ParseWorker(self.downloader, url)
        self._parse_thread.finished.connect(self._on_parse_success)
        self._parse_thread.error.connect(self._on_parse_error)
        self._parse_thread.start()

    def closeEvent(self, event):
        if self._parse_thread and self._parse_thread.isRunning():
            self._parse_thread.quit()
            self._parse_thread.wait(500)
        super().closeEvent(event)

    def _on_parse_success(self, items: List[ParsedMediaItem]):
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("🔍 解析資訊")
        self.current_parsed_items = items

        if not items:
            QMessageBox.warning(self, "解析結果", "未能在該網址找到可用的音訊或影片。")
            return

        first = items[0]
        self.preview_card.setVisible(True)

        if first.is_playlist:
            self.preview_title.setText(f"[播放清單: 共 {first.playlist_count} 支影片] {first.playlist_title}")
        else:
            self.preview_title.setText(first.title)

        extractor = first.extractor or "線上串流"
        dur_str = format_time(first.duration)
        res_summary = first.available_resolutions[0] if first.available_resolutions else "最高"

        self.preview_meta.setText(f"時長：{dur_str}  |  解析品質：{res_summary}  |  來源：{extractor}")
        self.preview_platform_tag.setText(f"▶ {extractor}")

        if first.available_resolutions:
            self.mp4_res_combo.clear()
            self.mp4_res_combo.addItems(first.available_resolutions)

        # Set thumbnail and duration badge
        if first.duration:
            self.thumb_widget.set_duration(dur_str)
        if first.thumbnail:
            self.thumb_widget.load_url(first.thumbnail)
        else:
            self.thumb_widget.show_placeholder()

    def _on_parse_error(self, err_msg: str):
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("🔍 解析資訊")
        self.thumb_widget.show_placeholder()
        QMessageBox.critical(self, "解析失敗", f"無法解析此網址：\n{err_msg}")

    def _start_download(self):
        cfg = self.config_mgr.get()
        out_dir = cfg.output_dir

        fmt = self.format_selector.get_selected_format().upper()
        is_video = fmt in ("MP4", "MKV", "WEBM", "MOV")
        mode = "mmd_wav" if fmt == "WAV" else ("video" if is_video else "audio")

        audio_q = "best"
        video_q = "best"
        sr = 44100
        ch = 2

        if fmt == "WAV":
            sr = 44100 if "44,100" in self.wav_sr_combo.currentText() else 48000
            ch = 2 if "Stereo" in self.wav_ch_combo.currentText() else 1
        elif fmt == "MP3":
            t = self.mp3_quality_combo.currentText()
            audio_q = "320k" if "320" in t else ("256k" if "256" in t else ("192k" if "192" in t else "128k"))
        elif fmt == "MP4":
            res_text = self.mp4_res_combo.currentText()
            digits = re.findall(r"\d+", res_text)
            video_q = digits[0] if digits else "best"
        elif fmt == "FLAC":
            audio_q = "best"
        elif fmt == "M4A":
            t = self.m4a_quality_combo.currentText()
            audio_q = "256k" if "256" in t else ("320k" if "320" in t else "192k")

        urls = []
        if self.batch_url_edit.isVisible():
            lines = self.batch_url_edit.toPlainText().splitlines()
            urls = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        else:
            single = self.url_input.text().strip()
            if single:
                urls = [single]

        if not urls:
            QMessageBox.warning(self, "無下載網址", "請輸入至少一個有效的影音網址！")
            return

        added_count = 0
        last_task = None
        for u in urls:
            last_task = self.task_manager.add_download_task(
                url=u,
                output_dir=out_dir,
                mode=mode,
                target_format=fmt,
                audio_quality=audio_q,
                video_quality=video_q,
                sample_rate=sr,
                channels=ch
            )
            added_count += 1

        if last_task:
            self._active_task_id = last_task.task_id
            self._show_active_task(last_task)

        ToastManager.show_toast(
            self,
            title="已加入下載佇列",
            message=f"已成功排入 {added_count} 筆「{fmt}」下載任務！",
            toast_type=ToastType.SUCCESS
        )

        if not self.batch_url_edit.isVisible():
            self.url_input.clear()

    # ---------------- Active Task Progress Section ----------------
    def _connect_task_signals(self):
        self.task_manager.signals.task_added.connect(self._on_task_added)
        self.task_manager.signals.task_updated.connect(self._on_task_updated)
        self.task_manager.signals.task_completed.connect(self._on_task_finished)
        self.task_manager.signals.task_failed.connect(self._on_task_finished)
        self.task_manager.signals.task_cancelled.connect(self._on_task_finished)

    def _on_task_added(self, task_id: str):
        task = self.task_manager.tasks.get(task_id)
        if task:
            self._active_task_id = task.task_id
            self._show_active_task(task)

    def _on_task_updated(self, task_id: str):
        if self._active_task_id == task_id:
            task = self.task_manager.tasks.get(task_id)
            if task:
                self._update_task_ui(task)

    def _on_task_finished(self, task_id: str):
        if self._active_task_id == task_id:
            task = self.task_manager.tasks.get(task_id)
            if task:
                self._update_task_ui(task)

    def _show_active_task(self, task: TaskItem):
        self.task_section.setVisible(True)
        running_count = len([t for t in self.task_manager.tasks.values() if t.status == TaskStatus.RUNNING])
        total_count = max(1, running_count)
        self.task_sec_title.setText(f"下載任務 ({total_count})")
        if hasattr(self, "thumb_widget") and self.thumb_widget._pixmap and not self.thumb_widget._pixmap.isNull():
            scaled_pix = self.thumb_widget._pixmap.scaled(
                56, 38, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.active_thumb.setPixmap(scaled_pix)
            self.active_thumb.setText("")
        self._update_task_ui(task)

    def _update_task_ui(self, task: TaskItem):
        self.active_title_lbl.setText(task.title or Path(task.source).name or "任務")
        if task.mode == "mmd_wav":
            self.active_sub_lbl.setText("WAV (PCM 16-bit / 44.1 kHz / Stereo)")
        elif task.mode == "video":
            self.active_sub_lbl.setText(f"{task.target_format} (完整影片)")
        else:
            self.active_sub_lbl.setText(f"{task.target_format} ({task.audio_quality})")

        pct = int(task.progress)
        self.active_progress_bar.setValue(pct)
        self.active_pct_lbl.setText(f"{pct}%")

        if getattr(task, "total_bytes", 0) > 0:
            self.active_bytes_lbl.setText(f"{format_bytes(task.downloaded_bytes)} / {format_bytes(task.total_bytes)}")
        elif getattr(task, "downloaded_bytes", 0) > 0:
            self.active_bytes_lbl.setText(format_bytes(task.downloaded_bytes))
        else:
            self.active_bytes_lbl.setText("")

        spd_val = task.speed
        spd_str = format_speed(spd_val) if isinstance(spd_val, (int, float)) and spd_val > 0 else (str(spd_val) if spd_val else "")
        eta_val = task.eta
        eta_str = format_time(eta_val) if isinstance(eta_val, (int, float)) and eta_val > 0 else (str(eta_val) if eta_val else "")

        if spd_str:
            self.active_speed_eta_lbl.setText(f"↓ {spd_str}  |  剩餘時間：約 {eta_str}" if eta_str else f"↓ {spd_str}")
        else:
            self.active_speed_eta_lbl.setText(task.message or "準備下載中...")

    def _cancel_active_task(self):
        if self._active_task_id:
            self.task_manager.cancel_task(self._active_task_id)

    def _on_theme_changed(self, mode: str, accent: str):
        if hasattr(self, "wav_bit_lbl"):
            self.wav_bit_lbl.setStyleSheet(f"color: {accent}; font-weight: bold;")
        if hasattr(self, "mp4_compat_label"):
            self.mp4_compat_label.setStyleSheet(f"color: {accent}; font-weight: bold;")
