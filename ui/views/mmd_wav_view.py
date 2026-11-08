"""
Hero View: MMD Compatible WAV Quick Processing Hub.
Offers a streamlined, 1-click experience for converting web media
or local files directly into verified MMD-standard WAV with modern Windows 11 Fluent Design.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.ffmpeg_engine import FFmpegEngine, MMDVerificationResult
from core.task_manager import TaskManager
from core.utils import format_time, parse_time_to_seconds
from ui.components.audio_player import AudioPlayerWidget
from ui.components.hero_banner import HeroBannerWidget
from ui.components.toast import ToastManager, ToastType
from ui.theme import ThemeManager


class MMDWavView(QWidget):
    """The central hero view dedicated to instant MMD WAV creation."""

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.theme_mgr = ThemeManager()
        self.ffmpeg_engine = self.task_manager.ffmpeg_engine

        self.selected_local_file: Optional[Path] = None
        self.latest_output_file: Optional[str] = None

        self._setup_ui()
        self.setAcceptDrops(True)
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_widget = QWidget()
        content_widget.setMinimumWidth(740)
        layout = QVBoxLayout(content_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 8, 16, 16)

        from PySide6.QtWidgets import QSizePolicy

        # 1. Page Header matching 01_mmd_wav_zone.png
        self.hero_banner = HeroBannerWidget(
            title="·|·  MMD WAV 專區",
            desc=[
                "一鍵將網路影音或本機音樂轉換為 MMD (MikuMikuDance) 完美相容的 WAV 格式。"
            ],
            badge_type="wav"
        )
        self.hero_banner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.hero_banner)

        # 2. Source Input Card (URL & Local File on single cohesive card)
        source_card = QFrame()
        source_card.setProperty("class", "card")
        source_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(16, 12, 16, 12)
        source_layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_title = QLabel("🔗  來源輸入")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        lbl_sub = QLabel("支援輸入網路影音連結，或選擇本機音樂檔案進行轉檔。")
        lbl_sub.setStyleSheet("font-size: 12px; color: #8E95A5; background: transparent;")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(lbl_sub)
        source_layout.addLayout(title_box)

        # Row 1: URL input
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        lbl_url = QLabel("🌐  影音網址：")
        lbl_url.setFixedWidth(82)
        lbl_url.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("貼上 YouTube、Bilibili、Niconico 或其他影音網址...")
        self.url_input.setFixedHeight(34)

        self.paste_url_btn = QPushButton("🔗 貼上並解析")
        self.paste_url_btn.setFixedHeight(34)
        self.paste_url_btn.setFixedWidth(100)
        self.paste_url_btn.clicked.connect(self._paste_url)

        row1.addWidget(lbl_url)
        row1.addWidget(self.url_input, 1)
        row1.addWidget(self.paste_url_btn)
        source_layout.addLayout(row1)

        # Divider: ――― 或 ―――
        divider_box = QHBoxLayout()
        divider_box.setContentsMargins(0, 2, 0, 2)
        divider_box.setSpacing(12)
        line_left = QFrame()
        line_left.setFrameShape(QFrame.Shape.HLine)
        line_left.setStyleSheet("color: #262A35; background-color: #262A35;")
        line_left.setFixedHeight(1)
        or_label = QLabel("或")
        or_label.setStyleSheet("color: #656D7E; font-size: 12px; background: transparent;")
        line_right = QFrame()
        line_right.setFrameShape(QFrame.Shape.HLine)
        line_right.setStyleSheet("color: #262A35; background-color: #262A35;")
        line_right.setFixedHeight(1)
        divider_box.addWidget(line_left, 1)
        divider_box.addWidget(or_label)
        divider_box.addWidget(line_right, 1)
        source_layout.addLayout(divider_box)

        # Row 2: Local file
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        lbl_file = QLabel("📄  本機檔案：")
        lbl_file.setFixedWidth(82)
        lbl_file.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        self.file_path_label = QLineEdit()
        self.file_path_label.setReadOnly(True)
        self.file_path_label.setPlaceholderText("未選擇檔案 (可匯入 MP3、MP4、FLAC、M4A 等常見格式)")
        self.file_path_label.setFixedHeight(34)

        self.browse_btn = QPushButton("📁 瀏覽檔案...")
        self.browse_btn.setFixedHeight(34)
        self.browse_btn.setFixedWidth(100)
        self.browse_btn.clicked.connect(self._browse_file)

        row2.addWidget(lbl_file)
        row2.addWidget(self.file_path_label, 1)
        row2.addWidget(self.browse_btn)
        source_layout.addLayout(row2)

        layout.addWidget(source_card)

        # 3. MMD Compatible Settings Card
        opt_card = QFrame()
        opt_card.setProperty("class", "card")
        opt_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        opt_card_layout = QVBoxLayout(opt_card)
        opt_card_layout.setContentsMargins(16, 14, 16, 14)
        opt_card_layout.setSpacing(12)

        self.opt_title = QLabel("🎛  MMD WAV 輸出設定 (建議依預設進行匯出)")
        self.opt_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        opt_card_layout.addWidget(self.opt_title)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        # Row 0: Sample rate & Channels
        lbl_sr = QLabel("採樣頻率：")
        lbl_sr.setFixedWidth(82)
        lbl_sr.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        self.sr_combo = QComboBox()
        self.sr_combo.addItems(["44,100 Hz (MMD 標準推薦)", "48,000 Hz"])
        self.sr_combo.setFixedHeight(34)

        lbl_ch = QLabel("聲道配置：")
        lbl_ch.setFixedWidth(82)
        lbl_ch.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        self.ch_combo = QComboBox()
        self.ch_combo.addItems(["Stereo 雙聲道 (MMD 預設)", "Mono 單聲道"])
        self.ch_combo.setFixedHeight(34)

        grid.addWidget(lbl_sr, 0, 0)
        grid.addWidget(self.sr_combo, 0, 1)
        grid.addWidget(lbl_ch, 0, 2)
        grid.addWidget(self.ch_combo, 0, 3)

        # Row 1: Bit Depth & Volume Gain
        lbl_bit = QLabel("位元深度：")
        lbl_bit.setFixedWidth(82)
        lbl_bit.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        self.bit_label = QLabel("16-bit Signed PCM (標準)")
        self.bit_label.setStyleSheet("font-weight: bold; color: #00D2B4; font-size: 13px;")

        lbl_gain = QLabel("音量增益 (dB)：")
        lbl_gain.setFixedWidth(110)
        lbl_gain.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(-24.0, 24.0)
        self.gain_spin.setValue(0.0)
        self.gain_spin.setSingleStep(0.5)
        self.gain_spin.setSuffix(" dB")
        self.gain_spin.setFixedHeight(34)

        grid.addWidget(lbl_bit, 1, 0)
        grid.addWidget(self.bit_label, 1, 1)
        grid.addWidget(lbl_gain, 1, 2)
        grid.addWidget(self.gain_spin, 1, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        # Row 2: Trimming & Checkboxes
        lbl_trim = QLabel("音訊裁切 (選用)：")
        lbl_trim.setFixedWidth(110)
        lbl_trim.setStyleSheet("color: #E1E4EA; font-size: 13px; background: transparent;")
        trim_box = QHBoxLayout()
        trim_box.setSpacing(6)
        self.trim_start_input = QLineEdit()
        self.trim_start_input.setPlaceholderText("開始 (例如 00:10)")
        self.trim_start_input.setFixedHeight(32)
        to_lbl = QLabel("至")
        to_lbl.setStyleSheet("color: #8E95A5; font-size: 12px; background: transparent;")
        self.trim_end_input = QLineEdit()
        self.trim_end_input.setPlaceholderText("結束 (例如 02:45)")
        self.trim_end_input.setFixedHeight(32)
        trim_box.addWidget(self.trim_start_input, 1)
        trim_box.addWidget(to_lbl)
        trim_box.addWidget(self.trim_end_input, 1)

        chk_box = QHBoxLayout()
        chk_box.setSpacing(14)
        self.silence_check = QCheckBox("移除前後靜音片段")
        self.norm_check = QCheckBox("音量正規化 (將音量調整至合理範圍)")
        chk_box.addWidget(self.silence_check)
        chk_box.addWidget(self.norm_check)

        trim_chk_row = QHBoxLayout()
        trim_chk_row.setSpacing(14)
        trim_chk_row.addWidget(lbl_trim)
        trim_chk_row.addLayout(trim_box, 1)
        trim_chk_row.addLayout(chk_box, 1)

        opt_card_layout.addLayout(grid)
        opt_card_layout.addLayout(trim_chk_row)
        layout.addWidget(opt_card)

        # 4. Full-Width Action Button: "📥 立即下載 / 轉檔為 MMD WAV"
        self.process_btn = QPushButton("📥 立即下載 / 轉檔為 MMD WAV")
        self.process_btn.setProperty("class", "primary")
        self.process_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.process_btn.setFixedHeight(42)
        self.process_btn.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.process_btn.clicked.connect(self._start_process)
        layout.addWidget(self.process_btn)

        # 5. Result Verification Card (Initially hidden until processed)
        self.result_card = QFrame()
        self.result_card.setProperty("class", "card")
        self.result_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.result_card.setVisible(False)
        self.result_layout = QVBoxLayout(self.result_card)
        self.result_layout.setContentsMargins(14, 12, 14, 12)
        self.result_layout.setSpacing(8)

        self.result_badge = QLabel("")
        self.result_badge.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.result_layout.addWidget(self.result_badge)

        self.details_label = QLabel("")
        self.details_label.setStyleSheet("font-size: 12px; line-height: 1.5; color: #A3AAB8;")
        self.result_layout.addWidget(self.details_label)

        result_btns = QHBoxLayout()
        self.result_open_btn = QPushButton("開啟檔案")
        self.result_folder_btn = QPushButton("開啟輸出資料夾")
        result_btns.addWidget(self.result_open_btn)
        result_btns.addWidget(self.result_folder_btn)
        result_btns.addStretch(1)
        self.result_layout.addLayout(result_btns)

        layout.addWidget(self.result_card)

        # 6. Audio Preview Player
        self.player_widget = AudioPlayerWidget(self.ffmpeg_engine)
        self.player_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.player_widget)

        layout.addStretch(1)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Connections
        self.result_open_btn.clicked.connect(self._open_result_file)
        self.result_folder_btn.clicked.connect(self._open_result_folder)

    def _paste_url(self):
        clip = QApplication.clipboard().text().strip()
        if clip:
            self.url_input.setText(clip)
            ToastManager.show_toast(
                self,
                title="已貼上網址",
                message=clip[:50] + ("..." if len(clip) > 50 else ""),
                toast_type=ToastType.INFO
            )

    def _on_theme_changed(self, mode: str, accent: str):
        is_dark = (mode == "dark")
        text_pri = "#FFFFFF" if is_dark else "#181A20"
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_pri}; background: transparent;")
        if hasattr(self, "opt_title"):
            self.opt_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_pri}; background: transparent;")
        if hasattr(self, "bit_label"):
            self.bit_label.setStyleSheet(f"font-weight: bold; color: {accent}; font-size: 13px;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            first_path = Path(urls[0].toLocalFile())
            if first_path.exists():
                self.selected_local_file = first_path
                self.file_path_label.setText(str(first_path))
                self.player_widget.load_audio(first_path)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選取音訊或影片檔案",
            "",
            "影音檔案 (*.mp3 *.mp4 *.flac *.m4a *.wav *.ogg *.opus *.mkv *.webm *.mov *.aac);;所有檔案 (*.*)"
        )
        if file_path:
            p = Path(file_path)
            self.selected_local_file = p
            self.file_path_label.setText(str(p))
            self.player_widget.load_audio(p)

    def _start_process(self):
        url = self.url_input.text().strip()
        local_file = self.selected_local_file if (self.selected_local_file and self.selected_local_file.exists()) else None

        if not url and not local_file:
            QMessageBox.warning(self, "未指定來源", "請先輸入影音網址，或瀏覽選取本機檔案！")
            return

        cfg = self.config_mgr.get()
        out_dir = cfg.output_dir

        sr = 44100 if "44,100" in self.sr_combo.currentText() else 48000
        ch = 2 if "Stereo" in self.ch_combo.currentText() else 1
        gain = self.gain_spin.value()
        t_start = parse_time_to_seconds(self.trim_start_input.text())
        t_end = parse_time_to_seconds(self.trim_end_input.text())
        rem_silence = self.silence_check.isChecked()
        norm = self.norm_check.isChecked()

        if local_file and local_file.exists():
            task = self.task_manager.add_convert_task(
                input_file=local_file,
                output_dir=out_dir,
                mode="mmd_wav",
                target_format="WAV",
                sample_rate=sr,
                channels=ch,
                volume_gain_db=gain,
                trim_start=t_start,
                trim_end=t_end,
                remove_silence=rem_silence,
                normalize=norm
            )
            ToastManager.show_toast(
                self,
                title="已加入 MMD WAV 轉檔佇列",
                message=f"已排程：「{local_file.name}」",
                toast_type=ToastType.SUCCESS
            )
        elif url:
            task = self.task_manager.add_download_task(
                url=url,
                output_dir=out_dir,
                mode="mmd_wav",
                target_format="WAV",
                sample_rate=sr,
                channels=ch,
                volume_gain_db=gain,
                trim_start=t_start,
                trim_end=t_end,
                remove_silence=rem_silence,
                normalize=norm
            )
            ToastManager.show_toast(
                self,
                title="已加入 MMD WAV 下載佇列",
                message="已開始在背景下載與處理，可至「任務管理」查看",
                toast_type=ToastType.SUCCESS
            )
            self.url_input.clear()

    def show_verification_result(self, task_output_file: str, verification: MMDVerificationResult):
        self.latest_output_file = task_output_file
        self.result_card.setVisible(True)

        if verification.is_valid:
            self.result_badge.setText("✓ MMD 相容標準驗證通過！ (可直接匯入 MMD 完美播放)")
            self.result_badge.setStyleSheet("color: #00E676; font-size: 14px; font-weight: bold;")
        else:
            self.result_badge.setText(f"⚠ MMD 驗證提示: {verification.message}")
            self.result_badge.setStyleSheet("color: #FFB300; font-size: 14px; font-weight: bold;")

        detail_text = "\n".join([f"• {k}: {v}" for k, v in verification.details.items()])
        self.details_label.setText(detail_text)

        p = Path(task_output_file)
        if p.exists():
            self.player_widget.load_audio(p)

    def _open_result_file(self):
        if self.latest_output_file and Path(self.latest_output_file).exists():
            import sys, subprocess, os
            if sys.platform == "win32":
                os.startfile(self.latest_output_file)
            else:
                subprocess.Popen(["xdg-open", self.latest_output_file])

    def _open_result_folder(self):
        if self.latest_output_file:
            import sys, subprocess
            p = Path(self.latest_output_file)
            if sys.platform == "win32":
                subprocess.Popen(f'explorer /select,"{p}"')
            else:
                subprocess.Popen(["xdg-open", str(p.parent)])
