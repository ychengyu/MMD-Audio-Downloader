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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.ffmpeg_engine import FFmpegEngine, MMDVerificationResult
from core.task_manager import TaskManager
from core.utils import format_time, parse_time_to_seconds
from ui.components.audio_player import AudioPlayerWidget
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
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(2, 2, 2, 2)

        # 1. Page Title Header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(3)

        self.hero_title = QLabel("||| MMD WAV 專區")
        self.hero_title.setStyleSheet("font-size: 22px; font-weight: bold; background: transparent;")

        self.hero_desc = QLabel(
            "一鍵產出 MikuMikuDance (MMD) 100% 完美相容之標準 WAV 音訊。\n"
            "嚴格遵循標準：Linear PCM 16-bit Signed (pcm_s16le) ． 44,100 Hz ． Stereo 雙聲道 ． 轉檔後經 ffprobe 嚴密檢驗！"
        )
        self.hero_desc.setStyleSheet("color: #A3AAB8; font-size: 12px; line-height: 1.4; background: transparent;")
        header_layout.addWidget(self.hero_title)
        header_layout.addWidget(self.hero_desc)
        layout.addWidget(header_widget)

        # 2. Source Selection (Dual Mode via Sleek Tabs)
        source_card = QFrame()
        source_card.setProperty("class", "card")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(14, 12, 14, 12)
        source_layout.setSpacing(10)

        source_title = QLabel("來源選取")
        source_title.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent;")
        source_layout.addWidget(source_title)

        self.source_tabs = QTabWidget()
        self.source_tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #343944; border-radius: 6px; padding: 10px; }")

        # Tab 1: Web URL
        tab_url = QWidget()
        tab_url_layout = QHBoxLayout(tab_url)
        tab_url_layout.setContentsMargins(4, 8, 4, 8)
        tab_url_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("貼上 YouTube、Bilibili、Niconico 或直連影音網址...")
        self.url_input.setMinimumHeight(36)

        self.paste_url_btn = QPushButton("📋 貼上")
        self.paste_url_btn.setMinimumHeight(36)
        self.paste_url_btn.clicked.connect(self._paste_url)

        self.clear_url_btn = QPushButton("清除")
        self.clear_url_btn.setMinimumHeight(36)
        self.clear_url_btn.clicked.connect(lambda: self.url_input.clear())

        tab_url_layout.addWidget(self.url_input, 1)
        tab_url_layout.addWidget(self.paste_url_btn)
        tab_url_layout.addWidget(self.clear_url_btn)
        self.source_tabs.addTab(tab_url, "🌐 網路影音網址")

        # Tab 2: Local File
        tab_file = QWidget()
        tab_file_layout = QHBoxLayout(tab_file)
        tab_file_layout.setContentsMargins(4, 8, 4, 8)
        tab_file_layout.setSpacing(8)

        self.file_path_label = QLabel("未選取檔案 (支援拖曳 MP3, MP4, FLAC, M4A 等至此處)")
        self.file_path_label.setStyleSheet("color: #A3AAB8; padding: 6px 10px; border-radius: 6px; border: 1px dashed #4A5260;")
        self.file_path_label.setMinimumHeight(36)

        self.browse_btn = QPushButton("📁 瀏覽檔案...")
        self.browse_btn.setMinimumHeight(36)
        self.browse_btn.clicked.connect(self._browse_file)

        tab_file_layout.addWidget(self.file_path_label, 1)
        tab_file_layout.addWidget(self.browse_btn)
        self.source_tabs.addTab(tab_file, "📂 本機影音檔案")

        source_layout.addWidget(self.source_tabs)
        layout.addWidget(source_card)

        # 3. MMD Compatible Settings (Compact 2 Rows)
        opt_group = QGroupBox("MMD 相容音訊參數設定 (預設最佳相容值)")
        opt_layout = QGridLayout(opt_group)
        opt_layout.setSpacing(10)
        opt_layout.setContentsMargins(14, 14, 14, 14)

        # Row 1: Sample Rate, Bit Depth, Channels
        opt_layout.addWidget(QLabel("採樣頻率:"), 0, 0)
        self.sr_combo = QComboBox()
        self.sr_combo.addItems(["44,100 Hz (MMD 標準音質)", "48,000 Hz"])
        opt_layout.addWidget(self.sr_combo, 0, 1)

        opt_layout.addWidget(QLabel("位元深度:"), 0, 2)
        self.bit_label = QLabel("16-bit Signed PCM (標準)")
        self.bit_label.setStyleSheet("font-weight: bold;")
        opt_layout.addWidget(self.bit_label, 0, 3)

        opt_layout.addWidget(QLabel("聲道配置:"), 0, 4)
        self.ch_combo = QComboBox()
        self.ch_combo.addItems(["Stereo 雙聲道 (MMD 預設)", "Mono 單聲道"])
        opt_layout.addWidget(self.ch_combo, 0, 5)

        # Row 2: Volume Gain, Trim, Checkboxes
        opt_layout.addWidget(QLabel("音量增益:"), 1, 0)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(-24.0, 24.0)
        self.gain_spin.setValue(0.0)
        self.gain_spin.setSingleStep(0.5)
        self.gain_spin.setSuffix(" dB")
        opt_layout.addWidget(self.gain_spin, 1, 1)

        opt_layout.addWidget(QLabel("音訊裁切:"), 1, 2)
        trim_box = QHBoxLayout()
        trim_box.setSpacing(4)
        self.trim_start_input = QLineEdit()
        self.trim_start_input.setPlaceholderText("開始 (如 00:10)")
        self.trim_end_input = QLineEdit()
        self.trim_end_input.setPlaceholderText("結束 (如 02:45)")
        trim_box.addWidget(self.trim_start_input)
        trim_box.addWidget(QLabel("至"))
        trim_box.addWidget(self.trim_end_input)
        opt_layout.addLayout(trim_box, 1, 3)

        check_box = QHBoxLayout()
        check_box.setSpacing(12)
        self.silence_check = QCheckBox("移除靜音")
        self.norm_check = QCheckBox("音量正規化")
        check_box.addWidget(self.silence_check)
        check_box.addWidget(self.norm_check)
        opt_layout.addLayout(check_box, 1, 4, 1, 2)

        layout.addWidget(opt_group)

        # 4. Full-Width Action Button
        self.process_btn = QPushButton("↓ 立即產出 MMD 相容 WAV")
        self.process_btn.setProperty("class", "primary")
        self.process_btn.setMinimumHeight(42)
        self.process_btn.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.process_btn.clicked.connect(self._start_process)
        layout.addWidget(self.process_btn)

        # 5. Result Verification Card (Initially hidden until processed)
        self.result_card = QFrame()
        self.result_card.setProperty("class", "card")
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
        layout.addWidget(self.player_widget)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Connections
        self.result_open_btn.clicked.connect(self._open_result_file)
        self.result_folder_btn.clicked.connect(self._open_result_folder)

        self._on_theme_changed("dark" if self.theme_mgr.is_dark() else "light", self.theme_mgr.accent_color)

    def _paste_url(self):
        clip = QApplication.clipboard().text().strip()
        if clip:
            self.url_input.setText(clip)

    def _on_theme_changed(self, mode: str, accent: str):
        self.hero_title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {accent}; background: transparent;")
        self.bit_label.setStyleSheet(f"font-weight: bold; color: {accent};")
        if self.selected_local_file:
            self.file_path_label.setStyleSheet(f"color: {accent}; padding: 6px 10px; border-radius: 6px; border: 1.5px solid {accent}; font-weight: bold;")
        else:
            self.file_path_label.setStyleSheet("color: #A3AAB8; padding: 6px 10px; border-radius: 6px; border: 1px dashed #4A5260;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            first_path = Path(urls[0].toLocalFile())
            if first_path.exists():
                self.selected_local_file = first_path
                accent = self.theme_mgr.accent_color
                self.file_path_label.setText(f"✓ 已選取: {first_path.name}")
                self.file_path_label.setStyleSheet(f"color: {accent}; padding: 6px 10px; border-radius: 6px; border: 1.5px solid {accent}; font-weight: bold;")
                self.source_tabs.setCurrentIndex(1)
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
            accent = self.theme_mgr.accent_color
            self.file_path_label.setText(f"✓ 已選取: {p.name}")
            self.file_path_label.setStyleSheet(f"color: {accent}; padding: 6px 10px; border-radius: 6px; border: 1.5px solid {accent}; font-weight: bold;")
            self.source_tabs.setCurrentIndex(1)
            self.player_widget.load_audio(p)

    def _start_process(self):
        is_url_tab = self.source_tabs.currentIndex() == 0
        url = self.url_input.text().strip() if is_url_tab else ""
        local_file = self.selected_local_file if not is_url_tab else None

        if is_url_tab and not url:
            QMessageBox.warning(self, "未指定網址", "請先輸入或貼上影音網址！")
            return
        elif not is_url_tab and (not local_file or not local_file.exists()):
            QMessageBox.warning(self, "未選取檔案", "請先選取或拖曳本機影音檔案！")
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
