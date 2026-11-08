"""
MMD Audio Downloader — 多功能影音下載與轉換器
Main Application Entry Point.
"""

import os
import sys
from pathlib import Path

# Set AppUserModelID for Windows 10/11 taskbar icon grouping
if sys.platform == "win32":
    try:
        import ctypes
        myappid = "MMD.AudioDownloader.App.1.0.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.utils import get_app_dir
from ui.main_window import MainWindow


def main():
    # Configure high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("MMD Audio Downloader")
    app.setApplicationDisplayName("MMD Audio Downloader")
    app.setOrganizationName("MMDStudio")

    # Set default system font for Windows Traditional Chinese
    default_font = app.font()
    default_font.setFamilies(["Segoe UI Variable", "Segoe UI", "Microsoft JhengHei UI", "Microsoft JhengHei", "sans-serif"])
    app.setFont(default_font)

    # Set application icon
    icon_path = get_app_dir() / "assets" / "app_icon.ico"
    if not icon_path.exists():
        for candidate in [
            Path(sys.executable).parent / "assets" / "app_icon.ico",
            Path(sys.executable).parent / "_internal" / "assets" / "app_icon.ico",
            Path(__file__).resolve().parent / "assets" / "app_icon.ico",
        ]:
            if candidate.exists():
                icon_path = candidate
                break
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
