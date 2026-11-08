"""
Automated PyInstaller Build Script for MMD Audio Downloader.
Packages the complete standalone Windows portable distribution with bundled
FFmpeg, ffprobe, yt-dlp, and assets.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 stdout on Windows terminals
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def build():
    root_dir = Path(__file__).resolve().parent
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    app_name = "MMD_Audio_Downloader"

    print("==================================================")
    print("  MMD Audio Downloader - Building Windows Release  ")
    print("==================================================")

    # 1. Terminate any running instances to avoid Windows file lock errors
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "MMD_Audio_Downloader.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "ffprobe.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # 2. Verify required source files and assets
    icon_path = root_dir / "assets" / "app_icon.ico"
    if not icon_path.exists():
        raise FileNotFoundError(f"找不到圖示檔案: {icon_path}")

    ffmpeg_bin = root_dir / "bin" / "ffmpeg.exe"
    ffprobe_bin = root_dir / "bin" / "ffprobe.exe"
    if not ffmpeg_bin.exists() or not ffprobe_bin.exists():
        raise FileNotFoundError("找不到 bin/ffmpeg.exe 或 bin/ffprobe.exe，請先放入 bin 資料夾中！")

    # 3. PyInstaller Command Arguments
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # No console window for GUI
        f"--name={app_name}",
        f"--icon={str(icon_path)}",
        f"--add-data={str(root_dir / 'assets')};assets",
        # Explicit hidden imports
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtMultimedia",
        "--hidden-import=yt_dlp",
        "--hidden-import=yt_dlp.extractor",
        "--hidden-import=yt_dlp.extractor._extractors",
        "--hidden-import=yt_dlp.downloader",
        "--hidden-import=yt_dlp.postprocessor",
        str(root_dir / "main.py")
    ]

    print("[Build] 正在執行 PyInstaller 打包程式...")
    subprocess.run(cmd, check=True)

    # 3. Post-build step: Copy bin/ directory into dist folder
    dist_app_dir = dist_dir / app_name
    target_bin_dir = dist_app_dir / "bin"
    target_bin_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Build] 正在複製 FFmpeg & ffprobe 至 {target_bin_dir}...")
    shutil.copy2(ffmpeg_bin, target_bin_dir / "ffmpeg.exe")
    shutil.copy2(ffprobe_bin, target_bin_dir / "ffprobe.exe")

    # Copy assets directly into dist root as well
    print(f"[Build] 正在複製 assets 資料夾至 {dist_app_dir / 'assets'}...")
    shutil.copytree(root_dir / "assets", dist_app_dir / "assets", dirs_exist_ok=True)

    # Copy README and license/info into dist
    readme_path = root_dir / "README.md"
    if readme_path.exists():
        shutil.copy2(readme_path, dist_app_dir / "README.md")

    # 4. Verification of output
    exe_path = dist_app_dir / f"{app_name}.exe"
    if not exe_path.exists():
        raise RuntimeError(f"打包完成但未找到主程式: {exe_path}")

    print("\n==================================================")
    print("  [SUCCESS] Windows Portable Build Complete!       ")
    print(f"  EXE Path: {exe_path}")
    print(f"  Dist Folder: {dist_app_dir}")
    print("==================================================")


if __name__ == "__main__":
    build()
