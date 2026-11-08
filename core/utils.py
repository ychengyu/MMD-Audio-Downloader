"""
Utility functions for MMD Audio Downloader.
Handles path safety, filename sanitization, size/time formatting, and system utilities.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


# Windows reserved base filenames
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Illegal characters in Windows filenames: \ / : * ? " < > | and control characters
ILLEGAL_CHARS_REGEX = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def get_app_dir() -> Path:
    """
    Get the base directory of the running application.
    Supports PyInstaller bundle (sys._MEIPASS or executable directory) and normal script execution.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            meipass = Path(sys._MEIPASS)
            if (meipass / "assets").exists():
                return meipass
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "assets").exists():
            return exe_dir
        if (exe_dir / "_internal" / "assets").exists():
            return exe_dir / "_internal"
        return exe_dir
    return Path(__file__).resolve().parent.parent


def get_bin_dir() -> Path:
    """
    Get the directory containing bundled binaries (ffmpeg, ffprobe).
    Checks both sys._MEIPASS (if onefile), the executable's folder/bin, and project bin/.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
        bin_dir = base_dir / "bin"
        if bin_dir.exists():
            return bin_dir
        if hasattr(sys, "_MEIPASS"):
            meipass_bin = Path(sys._MEIPASS) / "bin"
            if meipass_bin.exists():
                return meipass_bin
        return base_dir
    return get_app_dir() / "bin"


def sanitize_filename(filename: str, max_length: int = 200, replacement: str = "_") -> str:
    """
    Sanitize a filename so it is safe for Windows filesystems.
    Removes illegal characters, strips trailing spaces/dots, and handles reserved names.
    """
    if not filename:
        return "unnamed_media"

    # Replace illegal characters
    cleaned = ILLEGAL_CHARS_REGEX.sub(replacement, filename)

    # Replace consecutive spaces or replacements
    cleaned = re.sub(r'[\s]+', ' ', cleaned).strip(' .')

    if not cleaned:
        cleaned = "unnamed_media"

    # Check for reserved Windows filenames
    base_stem = Path(cleaned).stem.upper()
    if base_stem in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    # Truncate if too long (preserving extension)
    p = Path(cleaned)
    stem, ext = p.stem, p.suffix
    if len(stem) + len(ext) > max_length:
        stem = stem[: max_length - len(ext)]
        cleaned = stem + ext

    return cleaned


def get_unique_filename(target_path: Path) -> Path:
    """
    If target_path already exists, return a new Path with ' (1)', ' (2)', etc. appended.
    """
    if not target_path.exists():
        return target_path

    parent = target_path.parent
    stem = target_path.stem
    suffix = target_path.suffix
    counter = 1

    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def format_bytes(bytes_count: Optional[float]) -> str:
    """
    Format a byte count into a human-readable string (KB, MB, GB).
    """
    if bytes_count is None or bytes_count < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    val = float(bytes_count)

    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(val)} B"
    return f"{val:.2f} {units[unit_idx]}"


def format_speed(bytes_per_sec: Optional[float]) -> str:
    """
    Format bytes per second to human-readable speed.
    """
    if bytes_per_sec is None or bytes_per_sec <= 0:
        return "-- KB/s"
    return f"{format_bytes(bytes_per_sec)}/s"


def format_time(seconds: Optional[float]) -> str:
    """
    Format seconds to mm:ss or hh:mm:ss.
    """
    if seconds is None or seconds < 0:
        return "--:--"

    total_sec = int(round(seconds))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60

    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """
    Parse a time string like '01:23', '01:23.5', '00:01:23', or '83.5' into float seconds.
    Returns None if invalid.
    """
    if not time_str or not time_str.strip():
        return None

    time_str = time_str.strip()
    try:
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                mins, secs = parts
                return float(mins) * 60.0 + float(secs)
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return float(hrs) * 3600.0 + float(mins) * 60.0 + float(secs)
        return float(time_str)
    except ValueError:
        return None
