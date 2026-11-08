"""
Generates synthetic media test fixtures using FFmpeg.
Creates diverse formats, sample rates, channels, video files, and edge-case filenames.
"""

import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ffmpeg_engine import FFmpegEngine


def create_test_fixtures(fixtures_dir: Path) -> dict:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    engine = FFmpegEngine()
    ffmpeg = engine.ffmpeg_path
    cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    fixtures = {}

    # 1. MP3 file (Stereo 44.1kHz, 3s sine tone 440Hz)
    p_mp3 = fixtures_dir / "test_stereo_440hz.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k",
        str(p_mp3)
    ], check=True, creationflags=cflags)
    fixtures["mp3"] = p_mp3

    # 2. MP4 file with video & audio (Video: 320x240 testsrc2, Audio: 880Hz sine 3s)
    p_mp4 = fixtures_dir / "test_video_track.mp4"
    subprocess.run([
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest",
        str(p_mp4)
    ], check=True, creationflags=cflags)
    fixtures["mp4"] = p_mp4

    # 3. FLAC file (96kHz 24-bit high-res sine tone)
    p_flac = fixtures_dir / "test_highres_96k.flac"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=523:duration=2",
        "-ac", "2", "-ar", "96000", "-sample_fmt", "s32", "-c:a", "flac",
        str(p_flac)
    ], check=True, creationflags=cflags)
    fixtures["flac"] = p_flac

    # 4. Mono 48kHz WAV
    p_mono_48k = fixtures_dir / "test_mono_48k.wav"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=660:duration=2",
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le",
        str(p_mono_48k)
    ], check=True, creationflags=cflags)
    fixtures["mono_48k"] = p_mono_48k

    # 5. Low sample rate 22050Hz Mono
    p_low_sr = fixtures_dir / "test_low_22050.wav"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
        "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le",
        str(p_low_sr)
    ], check=True, creationflags=cflags)
    fixtures["low_sr"] = p_low_sr

    # 6. Chinese and special character filename MP3
    p_chinese = fixtures_dir / "【初音未來】測試音軌_MMD 特殊字元 #&! 繁體中文.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame",
        str(p_chinese)
    ], check=True, creationflags=cflags)
    fixtures["chinese"] = p_chinese

    # 7. Corrupted / broken media file (junk bytes)
    p_corrupt = fixtures_dir / "corrupted_media.mp3"
    with open(p_corrupt, "wb") as f:
        f.write(b"NOT_A_VALID_MEDIA_FILE_HEADER_GARBAGE_BYTES_1234567890")
    fixtures["corrupted"] = p_corrupt

    print(f"Created {len(fixtures)} test fixtures in {fixtures_dir}")
    return fixtures


if __name__ == "__main__":
    create_test_fixtures(Path(__file__).parent / "fixtures")
