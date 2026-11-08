"""
Main Window for MMD Audio Downloader.
Features modern Windows 11 Fluent Design, collapsible sidebar, top navigation bar,
instant theme hot-reloading, accent color synchronization, and view switching.
"""

from pathlib import Path
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.task_manager import TaskManager
from core.utils import get_app_dir
from ui.components.animated_stack import AnimatedStackedWidget
from ui.components.toast import ToastManager, ToastType
from ui.theme import PRESET_ACCENTS, ThemeManager
from ui.views.converter_view import ConverterView
from ui.views.download_view import DownloadView
from ui.views.mmd_wav_view import MMDWavView
from ui.views.settings_view import SettingsView
from ui.views.task_manager_view import TaskManagerView


VIEW_TITLES = [
    "MMD WAV 專區",
    "影音下載",
    "格式轉換",
    "任務管理",
    "軟體設定",
]


class MainWindow(QMainWindow):
    """Main application window with Fluent Design and collapsible sidebar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MMD Audio Downloader — 多功能影音下載與轉換器")
        self.resize(1180, 800)
        self.setMinimumSize(980, 680)

        # Set application icon
        icon_path = get_app_dir() / "assets" / "app_icon.ico"
        if not icon_path.exists():
            for candidate in [
                Path(sys.executable).parent / "assets" / "app_icon.ico",
                Path(sys.executable).parent / "_internal" / "assets" / "app_icon.ico",
                Path(__file__).resolve().parent.parent / "assets" / "app_icon.ico",
            ]:
                if candidate.exists():
                    icon_path = candidate
                    break
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.config_mgr = ConfigManager()
        cfg = self.config_mgr.get()
        self.task_manager = TaskManager(max_workers=cfg.max_concurrent_tasks)
        self.theme_mgr = ThemeManager()

        self.is_sidebar_collapsed = getattr(cfg, "sidebar_collapsed", False)

        self._setup_ui()
        self.theme_mgr.theme_changed.connect(self._on_theme_updated)
        self.theme_mgr.apply_theme(self)

    def _setup_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("central_widget")
        self.setCentralWidget(central_widget)

        root_v_layout = QVBoxLayout(central_widget)
        root_v_layout.setContentsMargins(0, 0, 0, 0)
        root_v_layout.setSpacing(0)

        # 1. Top Header Bar
        self.header_bar = QFrame()
        self.header_bar.setObjectName("top_header")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(12)

        # Left: App Brand & Icon
        brand_icon = QLabel()
        png_path = get_app_dir() / "assets" / "app_icon.png"
        if not png_path.exists():
            for candidate in [
                Path(sys.executable).parent / "assets" / "app_icon.png",
                Path(sys.executable).parent / "_internal" / "assets" / "app_icon.png",
                Path(__file__).resolve().parent.parent / "assets" / "app_icon.png",
            ]:
                if candidate.exists():
                    png_path = candidate
                    break
        if png_path.exists():
            pix = QPixmap(str(png_path)).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            brand_icon.setPixmap(pix)
        header_layout.addWidget(brand_icon)

        self.app_title_label = QLabel("MMD Audio Downloader")
        self.app_title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #F2F3F5;")
        header_layout.addWidget(self.app_title_label)

        # Page title reference for navigation & testing
        self.page_title_label = QLabel("·|· MMD WAV 專區")
        self.page_title_label.setVisible(False)
        header_layout.addWidget(self.page_title_label)

        header_layout.addStretch(1)

        # Quick Theme Mode Switcher (Dark / Light / System)
        self.quick_theme_btn = QPushButton("🌙 主題 ˇ" if self.theme_mgr.is_dark() else "☀️ 主題 ˇ")
        self.quick_theme_btn.setFixedHeight(30)
        self.quick_theme_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E212A;
                color: #C0C5D0;
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
        self.quick_theme_btn.clicked.connect(self._cycle_theme_mode)
        header_layout.addWidget(self.quick_theme_btn)

        # Quick Settings Button
        self.quick_settings_btn = QPushButton("⚙ 設定")
        self.quick_settings_btn.setFixedHeight(30)
        self.quick_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E212A;
                color: #C0C5D0;
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
        self.quick_settings_btn.clicked.connect(lambda: self._on_nav_clicked(4))
        header_layout.addWidget(self.quick_settings_btn)

        root_v_layout.addWidget(self.header_bar)

        # 2. Main Body: Sidebar + Views
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)

        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(12, 16, 12, 16)
        self.sidebar_layout.setSpacing(8)

        # Navigation Buttons Group
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []

        self.nav_items_data = [
            ("·|·  MMD WAV 專區", "·|·"),
            ("↓  影音下載", "↓"),
            ("⇄  格式轉換", "⇄"),
            ("📋  任務管理", "📋"),
            ("⚙  軟體設定", "⚙")
        ]

        for idx, (full_text, icon_char) in enumerate(self.nav_items_data):
            btn = QPushButton(full_text)
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "nav_button")
            btn.setToolTip(full_text)

            self.nav_group.addButton(btn, idx)
            self.nav_buttons.append(btn)
            self.sidebar_layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        self.sidebar_layout.addStretch(1)

        # Footer info matching mockup
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(4, 4, 4, 4)
        footer_layout.setSpacing(8)

        info_icon = QLabel("ℹ")
        info_icon.setStyleSheet("color: #6C7284; font-size: 14px; background: transparent;")
        info_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(info_icon)

        footer_text = QLabel("v1.0.0 正式版\nWindows 11")
        footer_text.setStyleSheet("color: #6C7284; font-size: 11px; line-height: 1.2; background: transparent;")
        footer_layout.addWidget(footer_text)
        footer_layout.addStretch(1)

        self.sidebar_layout.addWidget(footer_widget)

        body_layout.addWidget(self.sidebar)

        # 3. Content View Stack (with smooth micro-fade transition)
        self.stack = AnimatedStackedWidget()

        self.mmd_view = MMDWavView(self.task_manager)
        self.download_view = DownloadView(self.task_manager)
        self.converter_view = ConverterView(self.task_manager)
        self.tasks_view = TaskManagerView(self.task_manager)
        self.settings_view = SettingsView(self.task_manager)

        self.stack.addWidget(self.mmd_view)       # Index 0: MMD WAV (Hero)
        self.stack.addWidget(self.download_view)  # Index 1: Download
        self.stack.addWidget(self.converter_view) # Index 2: Converter
        self.stack.addWidget(self.tasks_view)     # Index 3: Task Manager
        self.stack.addWidget(self.settings_view)  # Index 4: Settings

        body_layout.addWidget(self.stack, 1)
        root_v_layout.addLayout(body_layout, 1)

        # Signal connections
        self.nav_group.idClicked.connect(self._on_nav_clicked)
        self.tasks_view.play_audio_requested.connect(self._play_in_mmd_view)
        self.task_manager.signals.task_completed.connect(self._on_task_finished)

    def _on_nav_clicked(self, idx: int):
        self.stack.set_current_index_animated(idx)
        if 0 <= idx < len(self.nav_buttons):
            self.nav_buttons[idx].setChecked(True)
        page_titles = [
            "·|· MMD WAV 專區",
            "↓ 影音下載",
            "⇄ 格式轉換",
            "📋 任務管理",
            "⚙ 軟體設定",
        ]
        if hasattr(self, "page_title_label") and 0 <= idx < len(page_titles):
            self.page_title_label.setText(page_titles[idx])

    def _toggle_sidebar(self):
        self.is_sidebar_collapsed = not self.is_sidebar_collapsed
        self.sidebar.setFixedWidth(64 if self.is_sidebar_collapsed else 200)

        for idx, (full_text, icon_char) in enumerate(self.nav_items_data):
            self.nav_buttons[idx].setText(icon_char if self.is_sidebar_collapsed else full_text)

        # Save preference
        cfg = self.config_mgr.get()
        cfg.sidebar_collapsed = self.is_sidebar_collapsed
        self.config_mgr.save(cfg)

    def _cycle_theme_mode(self):
        current = self.theme_mgr.theme_mode
        cycle = {"dark": "light", "light": "system", "system": "dark"}
        next_mode = cycle.get(current, "dark")
        self.theme_mgr.set_theme_mode(next_mode)
        self.quick_theme_btn.setText("🌙 主題 ˇ" if self.theme_mgr.is_dark() else "☀️ 主題 ˇ")

    def _on_theme_updated(self, mode: str, accent: str):
        # Hot-reload main window stylesheet
        self.setStyleSheet(self.theme_mgr.generate_stylesheet())
        if hasattr(self, "app_title_label"):
            self.app_title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {'#F2F3F5' if mode == 'dark' else '#181A20'};")
        if hasattr(self, "page_title_label"):
            is_dark = mode == "dark"
            self.page_title_label.setStyleSheet(f"color: {'#A0A5B5' if is_dark else '#4A5060'}; font-size: 13px; font-weight: 500;")

    def _play_in_mmd_view(self, file_path_str: str):
        if file_path_str == "__nav_mmd__":
            self.nav_buttons[0].setChecked(True)
            self._on_nav_clicked(0)
            return
        p = Path(file_path_str)
        if p.exists():
            self.mmd_view.player_widget.load_audio(p)
            self.nav_buttons[0].setChecked(True)
            self._on_nav_clicked(0)

    def _on_task_finished(self, task_id: str):
        task = self.task_manager.tasks.get(task_id)
        if task and task.mode == "mmd_wav" and task.output_file and task.is_mmd_valid is not None:
            from core.ffmpeg_engine import MMDVerificationResult
            res = MMDVerificationResult(
                is_valid=task.is_mmd_valid,
                codec="pcm_s16le",
                sample_rate=task.sample_rate,
                channels=task.channels,
                bit_depth=16,
                duration=0.0,
                format_name="wav",
                message=task.verification_msg,
                details=task.media_details
            )
            self.mmd_view.show_verification_result(task.output_file, res)

    def closeEvent(self, event):
        self.download_view.close()
        self.converter_view.close()
        super().closeEvent(event)
