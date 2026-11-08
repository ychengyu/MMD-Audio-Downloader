"""
Settings View for MMD Audio Downloader.
Configures output directory, download concurrency, Theme Mode (Dark/Light/System),
Theme Accent Color presets & custom HEX picker, core binary status, and yt-dlp update.
"""

import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.downloader_engine import DownloaderEngine
from core.ffmpeg_engine import FFmpegEngine
from core.task_manager import TaskManager
from ui.components.toast import ToastManager, ToastType
from ui.theme import PRESET_ACCENTS, ThemeManager


class UpdateWorker(QThread):
    finished = Signal(bool, str)

    def run(self):
        success, msg = DownloaderEngine.update_ytdlp()
        self.finished.emit(success, msg)


class SettingsView(QWidget):
    """View for adjusting software preferences and viewing system core statuses."""

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
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 4, 4, 4)

        # 1. Output Path Settings
        path_group = QGroupBox("檔案儲存與輸出路徑")
        path_layout = QHBoxLayout(path_group)
        self.out_dir_input = QLineEdit()
        self.browse_dir_btn = QPushButton("瀏覽路徑...")
        self.open_dir_btn = QPushButton("開啟資料夾")

        path_layout.addWidget(self.out_dir_input, 1)
        path_layout.addWidget(self.browse_dir_btn)
        path_layout.addWidget(self.open_dir_btn)
        layout.addWidget(path_group)

        # 2. Theme & Visual Style Settings
        theme_group = QGroupBox("介面外觀與主題色彩")
        theme_layout = QGridLayout(theme_group)
        theme_layout.setSpacing(12)

        # Theme Mode
        theme_layout.addWidget(QLabel("主題模式:"), 0, 0)
        self.theme_mode_combo = QComboBox()
        self.theme_mode_combo.addItems([
            "深色模式 (Dark)",
            "淺色模式 (Light)",
            "跟隨 Windows 系統模式 (System)"
        ])
        theme_layout.addWidget(self.theme_mode_combo, 0, 1)

        # Language
        theme_layout.addWidget(QLabel("介面語言:"), 0, 2)
        self.lang_lbl = QLabel("繁體中文 (台灣)")
        self.lang_lbl.setStyleSheet(f"color: {self.theme_mgr.accent_color}; font-weight: bold;")
        theme_layout.addWidget(self.lang_lbl, 0, 3)

        # Accent Color Presets
        theme_layout.addWidget(QLabel("主題強調色:"), 1, 0)
        accent_box = QHBoxLayout()
        accent_box.setSpacing(8)

        self.accent_buttons = {}
        for name, hex_code in PRESET_ACCENTS.items():
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_code};
                    color: #FFFFFF;
                    font-weight: bold;
                    border: 2px solid transparent;
                    border-radius: 6px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    border: 2px solid #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda checked, h=hex_code: self._set_accent(h))
            accent_box.addWidget(btn)
            self.accent_buttons[hex_code] = btn

        self.custom_color_btn = QPushButton("🎨 自訂顏色...")
        self.custom_color_btn.clicked.connect(self._pick_custom_color)
        accent_box.addWidget(self.custom_color_btn)
        accent_box.addStretch(1)

        theme_layout.addLayout(accent_box, 1, 1, 1, 3)

        # Current Accent Preview
        theme_layout.addWidget(QLabel("當前色彩:"), 2, 0)
        cur_color_box = QHBoxLayout()
        self.cur_color_preview = QLabel()
        self.cur_color_preview.setFixedSize(24, 24)
        self.cur_color_preview.setStyleSheet(f"background-color: {self.theme_mgr.accent_color}; border-radius: 12px; border: 1px solid #FFFFFF;")
        self.cur_color_hex = QLabel(self.theme_mgr.accent_color)
        self.cur_color_hex.setStyleSheet("font-weight: bold;")
        cur_color_box.addWidget(self.cur_color_preview)
        cur_color_box.addWidget(self.cur_color_hex)
        cur_color_box.addStretch(1)
        theme_layout.addLayout(cur_color_box, 2, 1)

        layout.addWidget(theme_group)

        # 3. Download & Task Preferences
        pref_group = QGroupBox("下載與並行任務設定")
        pref_layout = QGridLayout(pref_group)
        pref_layout.setSpacing(12)

        pref_layout.addWidget(QLabel("最大並行任務數:"), 0, 0)
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 10)
        self.concurrency_spin.setValue(3)
        pref_layout.addWidget(self.concurrency_spin, 0, 1)

        pref_layout.addWidget(QLabel("預設偏好格式:"), 0, 2)
        self.pref_fmt_combo = QComboBox()
        self.pref_fmt_combo.addItems(["WAV", "MP3", "MP4", "FLAC", "M4A", "MKV"])
        pref_layout.addWidget(self.pref_fmt_combo, 0, 3)

        layout.addWidget(pref_group)

        # 4. GPU Hardware Acceleration Settings (能用顯卡就用顯卡)
        gpu_group = QGroupBox("硬體加速與顯卡設定 (能用顯卡就用顯卡 ⚡)")
        gpu_layout = QVBoxLayout(gpu_group)
        gpu_layout.setSpacing(10)

        gpu_status_row = QHBoxLayout()
        self.gpu_status_icon = QLabel("⚡")
        self.gpu_status_icon.setStyleSheet("font-size: 18px;")
        self.gpu_status_label = QLabel("正在檢測顯示卡硬體加速支援...")
        self.gpu_status_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.gpu_retest_btn = QPushButton("🔄 重新檢測顯卡支援")
        self.gpu_retest_btn.setMaximumWidth(160)
        gpu_status_row.addWidget(self.gpu_status_icon)
        gpu_status_row.addWidget(self.gpu_status_label, 1)
        gpu_status_row.addWidget(self.gpu_retest_btn)
        gpu_layout.addLayout(gpu_status_row)

        self.gpu_details_label = QLabel()
        self.gpu_details_label.setStyleSheet("color: #8C95A6; font-size: 12px; line-height: 1.4;")
        self.gpu_details_label.setWordWrap(True)
        gpu_layout.addWidget(self.gpu_details_label)

        gpu_grid = QGridLayout()
        gpu_grid.setSpacing(10)

        self.gpu_enable_check = QCheckBox("啟用顯卡硬體加速 (自動優先調用 GPU 晶片，大幅縮短轉檔時間)")
        self.gpu_enable_check.setStyleSheet("font-weight: bold;")
        gpu_grid.addWidget(self.gpu_enable_check, 0, 0, 1, 2)

        gpu_grid.addWidget(QLabel("硬體加速偏好:"), 1, 0)
        self.gpu_backend_combo = QComboBox()
        self.gpu_backend_combo.addItems([
            "自動選擇最佳可用顯卡 (推薦)",
            "NVIDIA NVENC (GeForce / RTX 系列專用)",
            "Intel QuickSync (Intel 內顯 / Arc 系列專用)",
            "AMD AMF (Radeon 系列專用)",
            "停用顯卡 (強制使用 CPU 多核心軟體編碼)"
        ])
        gpu_grid.addWidget(self.gpu_backend_combo, 1, 1)

        gpu_layout.addLayout(gpu_grid)
        layout.addWidget(gpu_group)

        # 5. Core Engine Status (FFmpeg & yt-dlp)
        core_group = QGroupBox("影音核心元件狀態")
        core_layout = QVBoxLayout(core_group)
        core_layout.setSpacing(10)

        # FFmpeg status
        ffmpeg_row = QHBoxLayout()
        self.ffmpeg_status_label = QLabel("正在檢測 FFmpeg...")
        ffmpeg_row.addWidget(self.ffmpeg_status_label, 1)
        core_layout.addLayout(ffmpeg_row)

        # yt-dlp status
        ytdlp_row = QHBoxLayout()
        import yt_dlp
        self.ytdlp_version_label = QLabel(f"yt-dlp 版本: {yt_dlp.version.__version__}")
        self.update_ytdlp_btn = QPushButton("🔄 檢查並更新 yt-dlp")
        ytdlp_row.addWidget(self.ytdlp_version_label, 1)
        ytdlp_row.addWidget(self.update_ytdlp_btn)
        core_layout.addLayout(ytdlp_row)

        layout.addWidget(core_group)

        # 5. Save Button
        save_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 儲存並套用所有設定")
        self.save_btn.setProperty("class", "primary")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        save_layout.addStretch(1)
        save_layout.addWidget(self.save_btn)
        layout.addLayout(save_layout)

        # 6. About & License Info
        about_card = QFrame()
        about_card.setProperty("class", "card")
        about_layout = QVBoxLayout(about_card)
        about_title = QLabel("關於 MMD Audio Downloader v1.0.0")
        about_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        about_desc = QLabel(
            "專為 MikuMikuDance（MMD）動畫創作者與高品質音樂愛好者量身打造的桌面多媒體工具。\n"
            "轉檔核心採用 FFmpeg 靜態建置版本，網路串流下載由 yt-dlp 驅動。\n"
            "100% 本機運算、無廣告、無內購、無需註冊，重視使用者隱私安全。"
        )
        about_desc.setStyleSheet("color: #8C95A6; font-size: 12px; line-height: 1.5;")
        about_layout.addWidget(about_title)
        about_layout.addWidget(about_desc)
        layout.addWidget(about_card)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Signal connections
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

        # Mode index: 0=dark, 1=light, 2=system
        mode_map = {"dark": 0, "light": 1, "system": 2}
        self.theme_mode_combo.setCurrentIndex(mode_map.get(cfg.theme_mode, 0))

        # Preferred format
        pref = getattr(cfg, "preferred_format", "WAV") or "WAV"
        idx = self.pref_fmt_combo.findText(pref)
        if idx >= 0:
            self.pref_fmt_combo.setCurrentIndex(idx)

        # GPU acceleration preferences
        self.gpu_enable_check.setChecked(getattr(cfg, "use_gpu_acceleration", True))
        backend_map = {"auto": 0, "nvenc": 1, "qsv": 2, "amf": 3, "cpu": 4}
        self.gpu_backend_combo.setCurrentIndex(backend_map.get(getattr(cfg, "gpu_backend", "auto"), 0))

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
        border_col = "#FFFFFF" if self.theme_mgr.is_dark() else "#181A20"
        self.cur_color_preview.setStyleSheet(f"background-color: {hex_code}; border-radius: 12px; border: 2px solid {border_col};")
        self.cur_color_hex.setText(hex_code)
        if hasattr(self, "lang_lbl"):
            self.lang_lbl.setStyleSheet(f"color: {hex_code}; font-weight: bold;")

        hex_upper = hex_code.upper()
        for h, btn in self.accent_buttons.items():
            is_active = (h.upper() == hex_upper)
            btn.blockSignals(True)
            btn.setChecked(is_active)
            btn.blockSignals(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {h};
                    color: #FFFFFF;
                    font-weight: bold;
                    border: {3 if is_active else 1}px solid {'#FFFFFF' if is_active else 'transparent'};
                    border-radius: 6px;
                    padding: 6px 12px;
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

    def _check_ffmpeg(self):
        ok, msg = self.ffmpeg_engine.is_available()
        if ok:
            self.ffmpeg_status_label.setText(f"✓ FFmpeg 已就緒: {self.ffmpeg_engine.ffmpeg_path} ({msg})")
            self.ffmpeg_status_label.setStyleSheet("color: #00E676; font-weight: bold;")
        else:
            self.ffmpeg_status_label.setText(f"✕ FFmpeg 未找到或異常: {msg}")
            self.ffmpeg_status_label.setStyleSheet("color: #FF5252; font-weight: bold;")

    def _check_gpu(self, force_refresh: bool = False):
        info = self.ffmpeg_engine.detect_gpu_acceleration(force_refresh=force_refresh)
        if info.has_gpu:
            self.gpu_status_label.setText(f"✓ {info.name}")
            self.gpu_status_label.setStyleSheet("color: #00E676; font-weight: bold; font-size: 13px;")
            self.gpu_details_label.setText(f"{info.details}\n硬體加速編碼器：{info.h264_encoder} ｜ 支援格式：MP4、MOV 等視訊快速轉碼。")
        else:
            self.gpu_status_label.setText(f"ℹ {info.name}")
            self.gpu_status_label.setStyleSheet("color: #FFB300; font-weight: bold; font-size: 13px;")
            self.gpu_details_label.setText(info.details)

    def _retest_gpu(self):
        self._check_gpu(force_refresh=True)
        info = self.ffmpeg_engine.detect_gpu_acceleration()
        ToastManager.show_toast(
            self,
            title="顯卡檢測完成",
            message=self.gpu_status_label.text(),
            toast_type=ToastType.SUCCESS if info.has_gpu else ToastType.INFO
        )

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "選取輸出下載資料夾", self.out_dir_input.text())
        if folder:
            self.out_dir_input.setText(folder)

    def _open_dir(self):
        import os, subprocess
        p = self.out_dir_input.text().strip()
        if p and os.path.exists(p):
            if sys.platform == "win32":
                subprocess.Popen(f'explorer "{p}"')
            else:
                subprocess.Popen(["xdg-open", p])

    def _save_settings(self):
        cfg = self.config_mgr.get()
        cfg.output_dir = self.out_dir_input.text().strip()
        cfg.max_concurrent_tasks = self.concurrency_spin.value()
        cfg.preferred_format = self.pref_fmt_combo.currentText()

        # Save GPU acceleration options
        cfg.use_gpu_acceleration = self.gpu_enable_check.isChecked()
        backend_list = ["auto", "nvenc", "qsv", "amf", "cpu"]
        idx = self.gpu_backend_combo.currentIndex()
        cfg.gpu_backend = backend_list[idx] if idx < len(backend_list) else "auto"

        self.config_mgr.save(cfg)
        self.task_manager.set_max_workers(cfg.max_concurrent_tasks)
        self.ffmpeg_engine._cached_gpu_info = None
        self._check_gpu(force_refresh=True)

        ToastManager.show_toast(
            self,
            title="設定已儲存",
            message="所有偏好設定、顯卡加速與主題色彩已即時儲存並生效！",
            toast_type=ToastType.SUCCESS
        )

    def _trigger_ytdlp_update(self):
        self.update_ytdlp_btn.setEnabled(False)
        self.update_ytdlp_btn.setText("正在更新 yt-dlp...")

        self._update_thread = UpdateWorker()
        self._update_thread.finished.connect(self._on_update_finished)
        self._update_thread.start()

    def _on_update_finished(self, success: bool, msg: str):
        self.update_ytdlp_btn.setEnabled(True)
        self.update_ytdlp_btn.setText("🔄 檢查並更新 yt-dlp")
        if success:
            ToastManager.show_toast(self, "核心更新完成", msg, ToastType.SUCCESS)
            import yt_dlp
            self.ytdlp_version_label.setText(f"yt-dlp 版本: {yt_dlp.version.__version__}")
        else:
            QMessageBox.critical(self, "更新失敗", msg)
