"""
Unit & Integration Tests for DownloaderEngine.
Tests invalid URL error handling, yt-dlp direct media download, MMD WAV conversion,
video download with video+audio stream merging, and error translation.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.downloader_engine import DownloaderEngine, translate_download_error
from core.ffmpeg_engine import FFmpegEngine


@pytest.fixture
def downloader():
    engine = FFmpegEngine()
    return DownloaderEngine(engine)


def test_invalid_url_handling(downloader):
    """無效網址與網路錯誤處理測試"""
    invalid_url = "https://invalid-domain-does-not-exist-123456789.com/video"
    with pytest.raises(Exception) as exc_info:
        downloader.parse_url(invalid_url)
    assert len(str(exc_info.value)) > 0


def test_error_translation():
    """繁體中文錯誤翻譯測試"""
    e_bot = Exception("Sign in to confirm you’re not a bot to continue")
    assert "機器人驗證" in translate_download_error(e_bot)

    e_priv = Exception("This video is private")
    assert "私人影片" in translate_download_error(e_priv)

    e_unavail = Exception("Video unavailable in your country")
    assert "無法播放" in translate_download_error(e_unavail)

    e_403 = Exception("HTTP Error 403: Forbidden")
    assert "403" in translate_download_error(e_403)


def test_file_uri_download_and_mmd_wav(downloader, tmp_path):
    """測試從網址下載純音訊並轉換為 MMD WAV"""
    fix_dir = Path(__file__).parent / "fixtures"
    mp3_file = fix_dir / "test_stereo_440hz.mp3"
    file_url = mp3_file.resolve().as_uri()

    out_file, ver = downloader.download(
        url=file_url,
        output_dir=tmp_path / "dl_out",
        mode="mmd_wav"
    )

    assert out_file.exists()
    assert out_file.suffix == ".wav"
    assert ver is not None
    assert ver.is_valid is True
    assert ver.sample_rate == 44100
    assert ver.channels == 2
    assert ver.codec == "pcm_s16le"


def test_video_download_mp4(downloader, tmp_path):
    """測試完整影片下載 (MP4) 包含視訊與音訊軌道驗證"""
    fix_dir = Path(__file__).parent / "fixtures"
    mp4_file = fix_dir / "test_video_track.mp4"
    file_url = mp4_file.resolve().as_uri()

    out_file, ver = downloader.download(
        url=file_url,
        output_dir=tmp_path / "dl_video_mp4",
        mode="video",
        target_format="MP4"
    )

    assert out_file.exists()
    assert out_file.suffix == ".mp4"

    # Strict probe verification: must contain both video and audio streams
    probe = downloader.ffmpeg_engine.probe_media(out_file)
    assert probe.has_video is True, "MP4 輸出必須包含視訊軌"
    assert probe.has_audio is True, "MP4 輸出必須包含音訊軌"
    assert probe.video_stream is not None
    assert probe.audio_stream is not None
    assert probe.duration > 0


def test_video_download_mkv(downloader, tmp_path):
    """測試完整影片下載 (MKV) 包含視訊與音訊軌道驗證"""
    fix_dir = Path(__file__).parent / "fixtures"
    mp4_file = fix_dir / "test_video_track.mp4"
    file_url = mp4_file.resolve().as_uri()

    out_file, ver = downloader.download(
        url=file_url,
        output_dir=tmp_path / "dl_video_mkv",
        mode="video",
        target_format="MKV"
    )

    assert out_file.exists()
    assert out_file.suffix == ".mkv"

    probe = downloader.ffmpeg_engine.probe_media(out_file)
    assert probe.has_video is True
    assert probe.has_audio is True
