"""
Unit Tests for UI Components: ThumbnailWidget, FormatCardSelector, ThemeManager, and MainWindow.
"""

import sys
from pathlib import Path
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.components.animated_stack import AnimatedStackedWidget
from ui.components.empty_state import EmptyStateWidget
from ui.components.format_card_selector import FormatCardSelector
from ui.components.thumbnail_widget import ThumbnailWidget
from ui.components.toast import ToastManager, ToastType
from ui.main_window import MainWindow
from ui.theme import PRESET_ACCENTS, ThemeManager


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_theme_manager_modes_and_accents(qapp):
    """測試主題模式 (Dark/Light/System) 與強調色更換與 QSS 產出"""
    tm = ThemeManager()

    # Dark mode
    tm.set_theme_mode("dark")
    assert tm.is_dark() is True
    qss_dark = tm.generate_stylesheet()
    assert "#141519" in qss_dark

    # Light mode
    tm.set_theme_mode("light")
    assert tm.is_dark() is False
    qss_light = tm.generate_stylesheet()
    assert "#F5F6F9" in qss_light

    # Accent color presets
    for name, hex_code in PRESET_ACCENTS.items():
        tm.set_accent_color(hex_code)
        assert tm.accent_color == hex_code
        qss = tm.generate_stylesheet()
        assert hex_code in qss

    # Custom HEX color
    custom_pink = "#FF4081"
    tm.set_accent_color(custom_pink)
    assert tm.accent_color == custom_pink

    # Reset to default dark teal
    tm.set_theme_mode("dark")
    tm.set_accent_color("#00D2B4")


def test_format_card_selector(qapp):
    """測試卡片式格式選擇器切換與狀態回傳"""
    selector = FormatCardSelector(default_format="WAV")

    assert selector.get_selected_format() == "WAV"
    assert selector.is_selected_video() is False

    # Switch to MP4
    received = []
    selector.format_changed.connect(lambda fmt: received.append(fmt))

    selector.set_format("MP4")
    assert selector.get_selected_format() == "MP4"
    assert selector.is_selected_video() is True

    # Click card MP3
    selector.cards["MP3"].clicked.emit("MP3")
    assert selector.get_selected_format() == "MP3"
    assert selector.is_selected_video() is False
    assert "MP3" in received

    # Test card update_style in both Dark and Light modes
    tm = ThemeManager()
    tm.set_theme_mode("dark")
    selector.set_format("WAV")
    assert selector.cards["WAV"].is_selected is True
    assert selector.cards["MP3"].is_selected is False
    assert "#FFFFFF" in selector.cards["WAV"].title_label.styleSheet()

    tm.set_theme_mode("light")
    assert selector.cards["WAV"].is_selected is True
    assert "#181A20" in selector.cards["MP3"].title_label.styleSheet()


def test_thumbnail_widget_lifecycle(qapp):
    """測試縮圖元件初始化、狀態切換與清除"""
    widget = ThumbnailWidget(width=200, height=112)
    widget.show()
    assert "等待" in widget.status_text.text()

    # Test clear
    widget.clear()
    assert widget._pixmap is None
    assert not widget.status_text.isHidden()
    widget.close()


def test_main_window_sidebar_and_navigation(qapp):
    """測試主視窗側邊欄收合、導覽切換與主題更新"""
    win = MainWindow()

    # Navigation index checks
    assert win.stack.count() == 5
    win._on_nav_clicked(1)
    assert win.stack.currentIndex() == 1
    assert "影音下載" in win.page_title_label.text()

    win._on_nav_clicked(0)
    assert win.stack.currentIndex() == 0
    assert "MMD WAV" in win.page_title_label.text()

    # Sidebar collapse toggle
    initial_w = win.sidebar.width()
    win._toggle_sidebar()
    assert win.sidebar.width() < initial_w
    win._toggle_sidebar()
    assert win.sidebar.width() == initial_w

    # Theme switching on MainWindow
    win.theme_mgr.set_theme_mode("dark")
    assert win.theme_mgr.is_dark() is True
    assert "#141519" in win.styleSheet()

    win.theme_mgr.set_theme_mode("light")
    assert win.theme_mgr.is_dark() is False
    assert "#F5F6F9" in win.styleSheet()

    # Reset back to dark
    win.theme_mgr.set_theme_mode("dark")
    assert win.theme_mgr.is_dark() is True
    assert "#141519" in win.styleSheet()

    win.close()


def test_toast_system(qapp):
    """測試 Toast 通知建立、堆疊與淡出機制"""
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    parent.resize(800, 600)
    parent.show()

    toast = ToastManager.show_toast(
        parent=parent,
        title="測試標題",
        message="測試說明內容",
        toast_type=ToastType.SUCCESS,
        duration_ms=1000
    )
    assert toast is not None
    assert toast.isVisible() is True
    assert "測試標題" in toast.title_lbl.text()
    assert "測試說明內容" in toast.msg_lbl.text()

    # Manual close
    toast.close_btn.click()
    parent.close()


def test_empty_state_widget(qapp):
    """測試空狀態元件渲染與回呼觸發"""
    clicked = []
    widget = EmptyStateWidget(
        icon_text="📂",
        title="無檔案",
        description="請加入檔案",
        action_text="加入檔案",
        action_callback=lambda: clicked.append(True)
    )
    assert widget.title_lbl.text() == "無檔案"
    assert widget.desc_lbl.text() == "請加入檔案"
    assert widget.action_btn.text() == "加入檔案"

    widget.action_btn.click()
    assert len(clicked) == 1


def test_animated_stacked_widget(qapp):
    """測試動畫堆疊頁面切換與連續切換不衝突"""
    from PySide6.QtWidgets import QLabel
    stack = AnimatedStackedWidget()
    lbl1 = QLabel("Page 1")
    lbl2 = QLabel("Page 2")
    lbl3 = QLabel("Page 3")

    stack.addWidget(lbl1)
    stack.addWidget(lbl2)
    stack.addWidget(lbl3)

    assert stack.currentIndex() == 0

    # Animated switch to index 1
    stack.set_current_index_animated(1)
    assert stack.currentIndex() == 1

    # Rapid animated switch to index 2
    stack.set_current_index_animated(2)
    assert stack.currentIndex() == 2

