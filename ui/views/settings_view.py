"""
Settings View for MMD Audio Downloader.
Configures output directory, download concurrency, Theme Mode (Dark/Light/System),
Theme Accent Color presets & custom HEX picker, core binary status, and yt-dlp update
matching reference 05_settings_view.png.
"""

import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.downloader_engine import DownloaderEngine
from core.ffmpeg_engine import FFmpegEngine
from core.task_manager import TaskManager
from ui.components.hero_banner import HeroBannerWidget
from ui.components.toast import ToastManager, ToastType
from ui.theme import PRESET_ACCENTS, ThemeManager, adjust_color, get_contrast_text_color


class UpdateWorker(QThread):
    finished = Signal(bool, str)

    def run(self):
        success, msg = DownloaderEngine.update_ytdlp()
        self.finished.emit(success, msg)


class SettingsView(QWidget):
    """View for adjusting software preferences and viewing system core statuses matching 05_settings_view.png."""

    def __init__(self, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config_mgr = ConfigManager()
        self.theme_mgr = ThemeManager()
        self.ffmpeg_engine = self.task_manager.ffmpeg_engine
        self._update_thread = None

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. Page Header matching 05_settings_view.png
        self.hero_banner = HeroBannerWidget(
            title="⚙  軟體設定",
            desc=[
                "自訂 MMD Audio Downloader 的儲存位置、介面主題、色彩風格與下載參數。"
            ],
            badge_type="settings"
        )
        layout.addWidget(self.hero_banner)

        # Card 1: 📁 下載與輸出目錄設定
        card1 = QFrame()
        card1.setProperty("class", "card")
        c1_layout = QVBoxLayout(card1)
        c1_layout.setContentsMargins(16, 14, 16, 14)
        c1_layout.setSpacing(10)

        c1_title = QLabel("📁  下載與輸出目錄設定")
        c1_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        c1_layout.addWidget(c1_title)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        lbl_dir = QLabel("預設儲存目錄：")
        lbl_dir.setFixedWidth(100)
        lbl_dir.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")

        self.out_dir_input = QLineEdit()
        self.out_dir_input.setFixedHeight(34)

        self.browse_dir_btn = QPushButton("📁 瀏覽...")
        self.browse_dir_btn.setFixedHeight(34)
        self.browse_dir_btn.setFixedWidth(85)

        self.open_dir_btn = QPushButton("📂 開啟資料夾")
        self.open_dir_btn.setFixedHeight(34)
        self.open_dir_btn.setFixedWidth(105)

        row1.addWidget(lbl_dir)
        row1.addWidget(self.out_dir_input, 1)
        row1.addWidget(self.browse_dir_btn)
        row1.addWidget(self.open_dir_btn)
        c1_layout.addLayout(row1)

        layout.addWidget(card1)

        # Card 2: 🎨 介面外觀與主題色彩
        card2 = QFrame()
        card2.setProperty("class", "card")
        c2_layout = QVBoxLayout(card2)
        c2_layout.setContentsMargins(16, 14, 16, 14)
        c2_layout.setSpacing(12)

        c2_title = QLabel("🎨  介面外觀與主題色彩")
        c2_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        c2_layout.addWidget(c2_title)

        grid2 = QGridLayout()
        grid2.setSpacing(10)
        grid2.setContentsMargins(0, 0, 0, 0)

        # Theme Mode
        lbl_tm = QLabel("主題模式：")
        lbl_tm.setFixedWidth(85)
        lbl_tm.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid2.addWidget(lbl_tm, 0, 0)

        self.theme_mode_combo = QComboBox()
        self.theme_mode_combo.setFixedHeight(32)
        self.theme_mode_combo.addItems([
            "深色模式 (Dark)",
            "淺色模式 (Light)",
            "跟隨 Windows 系統模式 (System)"
        ])
        grid2.addWidget(self.theme_mode_combo, 0, 1)

        # Language
        lbl_lang = QLabel("介面語言：")
        lbl_lang.setFixedWidth(75)
        lbl_lang.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid2.addWidget(lbl_lang, 0, 2)

        self.lang_lbl = QLabel("繁體中文 (台灣)")
        self.lang_lbl.setStyleSheet(f"color: {self.theme_mgr.accent_color}; font-weight: bold; background: transparent;")
        grid2.addWidget(self.lang_lbl, 0, 3)

        # Accent Buttons
        lbl_accent = QLabel("主題強調色：")
        lbl_accent.setFixedWidth(85)
        lbl_accent.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid2.addWidget(lbl_accent, 1, 0)

        accent_box = QHBoxLayout()
        accent_box.setSpacing(8)
        self.accent_buttons = {}
        for name, hex_code in PRESET_ACCENTS.items():
            btn = QPushButton(name)
            btn.setFixedHeight(30)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, h=hex_code: self._set_accent(h))
            accent_box.addWidget(btn)
            self.accent_buttons[hex_code] = btn

        self.custom_color_btn = QPushButton("🎨 自訂顏色...")
        self.custom_color_btn.setFixedHeight(30)
        self.custom_color_btn.clicked.connect(self._pick_custom_color)
        accent_box.addWidget(self.custom_color_btn)
        accent_box.addStretch(1)

        grid2.addLayout(accent_box, 1, 1, 1, 3)

        # Current Accent Preview
        lbl_cur = QLabel("當前色彩：")
        lbl_cur.setFixedWidth(85)
        lbl_cur.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid2.addWidget(lbl_cur, 2, 0)

        cur_box = QHBoxLayout()
        cur_box.setSpacing(8)
        self.cur_color_preview = QLabel()
        self.cur_color_preview.setFixedSize(20, 20)
        self.cur_color_preview.setStyleSheet(f"background-color: {self.theme_mgr.accent_color}; border-radius: 10px; border: 1px solid #FFFFFF;")
        self.cur_color_hex = QLabel(self.theme_mgr.accent_color)
        self.cur_color_hex.setStyleSheet("font-weight: bold; background: transparent;")
        cur_box.addWidget(self.cur_color_preview)
        cur_box.addWidget(self.cur_color_hex)
        cur_box.addStretch(1)

        grid2.addLayout(cur_box, 2, 1)

        c2_layout.addLayout(grid2)
        layout.addWidget(card2)

        # Card 3: ⚙ 下載與任務設定
        card3 = QFrame()
        card3.setProperty("class", "card")
        c3_layout = QVBoxLayout(card3)
        c3_layout.setContentsMargins(16, 14, 16, 14)
        c3_layout.setSpacing(12)

        c3_title = QLabel("⚙  下載與任務設定")
        c3_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        c3_layout.addWidget(c3_title)

        grid3 = QGridLayout()
        grid3.setSpacing(10)
        grid3.setContentsMargins(0, 0, 0, 0)

        # Concurrency
        lbl_conc = QLabel("最大並行任務數：")
        lbl_conc.setFixedWidth(115)
        lbl_conc.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid3.addWidget(lbl_conc, 0, 0)
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 8)
        self.concurrency_spin.setValue(3)
        self.concurrency_spin.setFixedHeight(30)
        grid3.addWidget(self.concurrency_spin, 0, 1)

        # Preferred format
        lbl_pref = QLabel("預設首選格式：")
        lbl_pref.setFixedWidth(100)
        lbl_pref.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid3.addWidget(lbl_pref, 0, 2)
        self.pref_fmt_combo = QComboBox()
        self.pref_fmt_combo.setFixedHeight(30)
        self.pref_fmt_combo.addItems(["WAV (MMD 專用)", "MP3", "MP4", "FLAC", "M4A", "MKV"])
        grid3.addWidget(self.pref_fmt_combo, 0, 3)

        # GPU acceleration check & backend
        lbl_gpu = QLabel("硬體編碼加速：")
        lbl_gpu.setFixedWidth(115)
        lbl_gpu.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid3.addWidget(lbl_gpu, 1, 0)

        gpu_box = QHBoxLayout()
        gpu_box.setSpacing(8)
        self.gpu_enable_check = QCheckBox("啟用 GPU 顯卡編碼加速 (優先使用 NVENC / QSV / AMF)")
        self.gpu_enable_check.setChecked(True)
        gpu_box.addWidget(self.gpu_enable_check)
        grid3.addLayout(gpu_box, 1, 1, 1, 3)

        c3_layout.addLayout(grid3)
        layout.addWidget(card3)

        # Card 4: </> 影音核心元件狀態
        card4 = QFrame()
        card4.setProperty("class", "card")
        c4_layout = QVBoxLayout(card4)
        c4_layout.setContentsMargins(16, 14, 16, 14)
        c4_layout.setSpacing(10)

        c4_title = QLabel("</>  影音核心元件狀態")
        c4_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        c4_layout.addWidget(c4_title)

        grid4 = QGridLayout()
        grid4.setSpacing(10)
        grid4.setContentsMargins(0, 0, 0, 0)

        # FFmpeg status
        lbl_ff = QLabel("FFmpeg 轉碼核心：")
        lbl_ff.setFixedWidth(120)
        lbl_ff.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid4.addWidget(lbl_ff, 0, 0)
        self.ffmpeg_status_lbl = QLabel("檢查中...")
        self.ffmpeg_status_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        grid4.addWidget(self.ffmpeg_status_lbl, 0, 1)

        # GPU Status
        lbl_gpus = QLabel("GPU 顯卡加速：")
        lbl_gpus.setFixedWidth(120)
        lbl_gpus.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid4.addWidget(lbl_gpus, 1, 0)
        self.gpu_status_lbl = QLabel("偵測中...")
        self.gpu_status_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        grid4.addWidget(self.gpu_status_lbl, 1, 1)

        self.gpu_retest_btn = QPushButton("🔄 重新檢測")
        self.gpu_retest_btn.setFixedHeight(28)
        self.gpu_retest_btn.setFixedWidth(95)
        grid4.addWidget(self.gpu_retest_btn, 1, 2)

        # yt-dlp Status
        lbl_yt = QLabel("yt-dlp 解析模組：")
        lbl_yt.setFixedWidth(120)
        lbl_yt.setStyleSheet("color: #CAD1DC; font-size: 13px; background: transparent;")
        grid4.addWidget(lbl_yt, 2, 0)
        self.ytdlp_status_lbl = QLabel("就緒 (支援 YouTube, Bilibili, Niconico)")
        self.ytdlp_status_lbl.setStyleSheet("color: #00E676; font-weight: bold; background: transparent;")
        grid4.addWidget(self.ytdlp_status_lbl, 2, 1)

        self.update_ytdlp_btn = QPushButton("🔄 檢查更新")
        self.update_ytdlp_btn.setFixedHeight(28)
        self.update_ytdlp_btn.setFixedWidth(95)
        grid4.addWidget(self.update_ytdlp_btn, 2, 2)

        c4_layout.addLayout(grid4)
        layout.addWidget(card4)

        # Card 5: ℹ 關於 MMD Audio Downloader
        card5 = QFrame()
        card5.setProperty("class", "card")
        c5_layout = QVBoxLayout(card5)
        c5_layout.setContentsMargins(16, 14, 16, 14)
        c5_layout.setSpacing(6)

        c5_title = QLabel("ℹ  關於 MMD Audio Downloader")
        c5_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; background: transparent;")
        c5_layout.addWidget(c5_title)

        about_desc = QLabel(
            "MMD Audio Downloader v1.0.0 正式版 — 專為 MMD 創作者打造的現代化影音處理工具。\n"
            "開源授權: MIT License · 免費開源 · 支援 44.1 kHz 16-bit PCM WAV 完美相容規格。\n"
            "專案首頁: https://github.com/ychengyu/MMD-Audio-Downloader"
        )
        about_desc.setStyleSheet("color: #8E95A5; font-size: 12px; line-height: 1.6; background: transparent;")
        c5_layout.addWidget(about_desc)
        layout.addWidget(card5)

        # Full-width Save Button
        self.save_btn = QPushButton("💾 儲存並套用所有設定")
        self.save_btn.setFixedHeight(42)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00D2B4;
                color: #0E151B;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1AE0C4;
            }
            QPushButton:pressed {
                background-color: #00BFA3;
            }
        """)
        layout.addWidget(self.save_btn)

        layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Connections
        self.browse_dir_btn.clicked.connect(self._browse_dir)
        self.open_dir_btn.clicked.connect(self._open_dir)
        self.save_btn.clicked.connect(self._save_settings)
        self.update_ytdlp_btn.clicked.connect(self._trigger_ytdlp_update)
        self.gpu_retest_btn.clicked.connect(self._retest_gpu)
        self.theme_mode_combo.currentIndexChanged.connect(self._on_theme_mode_changed)
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

        self._check_ffmpeg()
        self._check_gpu()

    def _load_values(self):
        cfg = self.config_mgr.get()
        self.out_dir_input.setText(cfg.output_dir)
        self.concurrency_spin.setValue(cfg.max_concurrent_tasks)

        mode_map = {"dark": 0, "light": 1, "system": 2}
        self.theme_mode_combo.setCurrentIndex(mode_map.get(cfg.theme_mode, 0))

        pref = getattr(cfg, "preferred_format", "WAV") or "WAV"
        for i in range(self.pref_fmt_combo.count()):
            if pref in self.pref_fmt_combo.itemText(i):
                self.pref_fmt_combo.setCurrentIndex(i)
                break

        self.gpu_enable_check.setChecked(getattr(cfg, "use_gpu_acceleration", True))
        self._update_accent_preview(self.theme_mgr.accent_color)
        self._check_gpu()

    def _set_accent(self, hex_code: str):
        self.theme_mgr.set_accent_color(hex_code)
        self._update_accent_preview(hex_code)

    def _pick_custom_color(self):
        initial = QColor(self.theme_mgr.accent_color)
        col = QColorDialog.getColor(initial, self, "選取自訂主題強調色彩")
        if col.isValid():
            hex_code = col.name().upper()
            self._set_accent(hex_code)

    def _update_accent_preview(self, hex_code: str):
        self.cur_color_preview.setStyleSheet(f"background-color: {hex_code}; border-radius: 10px; border: 1px solid #FFFFFF;")
        self.cur_color_hex.setText(hex_code)
        if hasattr(self, "lang_lbl"):
            self.lang_lbl.setStyleSheet(f"color: {hex_code}; font-weight: bold; background: transparent;")

        hex_upper = hex_code.upper()
        for h, btn in self.accent_buttons.items():
            is_active = (h.upper() == hex_upper)
            btn.blockSignals(True)
            btn.setChecked(is_active)
            btn.blockSignals(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {h};
                    color: {get_contrast_text_color(h)};
                    font-weight: bold;
                    border: {3 if is_active else 1}px solid {'#FFFFFF' if is_active else 'transparent'};
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border: 2px solid #FFFFFF;
                }}
            """)

    def _on_theme_mode_changed(self, idx: int):
        modes = ["dark", "light", "system"]
        mode = modes[idx] if idx < len(modes) else "dark"
        self.theme_mgr.set_theme_mode(mode)

    def _on_theme_changed(self, mode: str, accent: str):
        mode_map = {"dark": 0, "light": 1, "system": 2}
        cur_mode = self.theme_mgr.theme_mode
        target_idx = mode_map.get(cur_mode, 0)
        self.theme_mode_combo.blockSignals(True)
        self.theme_mode_combo.setCurrentIndex(target_idx)
        self.theme_mode_combo.blockSignals(False)

        self._update_accent_preview(accent)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: {get_contrast_text_color(accent)};
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {adjust_color(accent, 1.12)};
            }}
            QPushButton:pressed {{
                background-color: {adjust_color(accent, 0.88)};
            }}
        """)

    def _check_ffmpeg(self):
        ok, msg = self.ffmpeg_engine.is_available()
        if ok:
            self.ffmpeg_status_lbl.setText("✓ 正常就緒 (已載入 FFmpeg / ffprobe 核心模組)")
            self.ffmpeg_status_lbl.setStyleSheet("color: #00E676; font-weight: bold; background: transparent;")
        else:
            self.ffmpeg_status_lbl.setText("✕ 轉碼核心異常")
            self.ffmpeg_status_lbl.setStyleSheet("color: #FF5252; font-weight: bold; background: transparent;")

    def _check_gpu(self):
        gpu_info = self.ffmpeg_engine.detect_gpu_acceleration(force_refresh=True)
        if gpu_info.has_gpu and self.gpu_enable_check.isChecked():
            self.gpu_status_lbl.setText(f"✓ 已啟用 ({gpu_info.name})")
            self.gpu_status_lbl.setStyleSheet("color: #00D2B4; font-weight: bold; background: transparent;")
        else:
            self.gpu_status_lbl.setText("● CPU 多核心模式 (未啟用顯卡硬體加速)")
            self.gpu_status_lbl.setStyleSheet("color: #CAD1DC; font-weight: bold; background: transparent;")

    def _retest_gpu(self):
        self.gpu_status_lbl.setText("檢測中...")
        self.gpu_status_lbl.setStyleSheet("color: #FFB300; font-weight: bold; background: transparent;")
        self._check_gpu()
        ToastManager.show_toast(
            self,
            title="GPU 檢測完成",
            message=self.gpu_status_lbl.text(),
            toast_type=ToastType.INFO
        )

    def _browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "選取輸出目錄", self.out_dir_input.text())
        if dir_path:
            self.out_dir_input.setText(dir_path)

    def _open_dir(self):
        p = self.out_dir_input.text().strip()
        if p and Path(p).exists():
            if sys.platform == "win32":
                os.startfile(p)
            else:
                subprocess.Popen(["xdg-open", p])
        else:
            QMessageBox.warning(self, "路徑不存在", f"目錄不存在:\n{p}")

    def _trigger_ytdlp_update(self):
        self.update_ytdlp_btn.setEnabled(False)
        self.update_ytdlp_btn.setText("檢查中...")
        self._update_thread = UpdateWorker()
        self._update_thread.finished.connect(self._on_update_finished)
        self._update_thread.start()

    def _on_update_finished(self, success: bool, msg: str):
        self.update_ytdlp_btn.setEnabled(True)
        self.update_ytdlp_btn.setText("🔄 檢查更新")
        if success:
            ToastManager.show_toast(self, title="解析模組更新", message=msg, toast_type=ToastType.SUCCESS)
        else:
            ToastManager.show_toast(self, title="解析模組資訊", message=msg, toast_type=ToastType.INFO)

    def _save_settings(self):
        out_dir = self.out_dir_input.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "輸入錯誤", "輸出目錄不能為空！")
            return

        cfg = self.config_mgr.get()
        cfg.output_dir = out_dir
        cfg.max_concurrent_tasks = self.concurrency_spin.value()
        cfg.use_gpu_acceleration = self.gpu_enable_check.isChecked()

        pref_map = ["WAV", "MP3", "MP4", "FLAC", "M4A", "MKV"]
        idx = self.pref_fmt_combo.currentIndex()
        if 0 <= idx < len(pref_map):
            cfg.preferred_format = pref_map[idx]

        self.config_mgr.save(cfg)
        self._check_gpu()

        ToastManager.show_toast(
            self,
            title="設定已成功儲存",
            message="所有設定值已寫入設定檔並即時套用生效！",
            toast_type=ToastType.SUCCESS
        )
