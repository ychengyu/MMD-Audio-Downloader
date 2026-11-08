"""
Unit & Integration Tests for FFmpegEngine and MMD WAV Verification.
Verifies all audio conversion modes, channel mapping, sample rate resampling,
metadata probing, and low-level RIFF/WAVE header compliance for MikuMikuDance.
"""

import struct
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ffmpeg_engine import FFmpegEngine, MMDVerificationResult
from tests.create_fixtures import create_test_fixtures


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    fix_dir = Path(__file__).parent / "fixtures"
    if not (fix_dir / "test_stereo_440hz.mp3").exists():
        return create_test_fixtures(fix_dir)
    return {
        "mp3": fix_dir / "test_stereo_440hz.mp3",
        "mp4": fix_dir / "test_video_track.mp4",
        "flac": fix_dir / "test_highres_96k.flac",
        "mono_48k": fix_dir / "test_mono_48k.wav",
        "low_sr": fix_dir / "test_low_22050.wav",
        "chinese": fix_dir / "【初音未來】測試音軌_MMD 特殊字元 #&! 繁體中文.mp3",
        "corrupted": fix_dir / "corrupted_media.mp3"
    }


@pytest.fixture
def engine():
    return FFmpegEngine()


def verify_riff_wave_binary_header(wav_path: Path):
    """
    Low-level binary inspection of the WAV file header to guarantee 100% MikuMikuDance compatibility:
    - 0x00: 'RIFF'
    - 0x08: 'WAVE'
    - 'fmt ' chunk:
        - Audio format = 1 (Linear PCM, no compression/ADPCM/float)
        - Num channels = 2 (Stereo)
        - Sample rate = 44100 Hz
        - Bits per sample = 16
    """
    with open(wav_path, "rb") as f:
        riff_tag = f.read(4)
        assert riff_tag == b"RIFF", f"Invalid RIFF header: {riff_tag}"
        _ = f.read(4)  # file size - 8
        wave_tag = f.read(4)
        assert wave_tag == b"WAVE", f"Invalid WAVE format tag: {wave_tag}"

        # Search for fmt chunk
        found_fmt = False
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                # fmt chunk layout: audio_format(2), channels(2), sample_rate(4), byte_rate(4), block_align(2), bits_per_sample(2)
                audio_fmt, num_ch, sr, byte_rate, block_align, bits = struct.unpack("<HHIIHH", fmt_data[:16])
                assert audio_fmt == 1, f"Audio format must be 1 (PCM), got {audio_fmt}"
                assert num_ch == 2, f"Channels must be 2 (Stereo), got {num_ch}"
                assert sr == 44100, f"Sample rate must be 44100, got {sr}"
                assert bits == 16, f"Bits per sample must be 16, got {bits}"
                found_fmt = True
                break
            else:
                f.seek(chunk_size, 1)  # Skip unknown chunk

        assert found_fmt, "WAV file does not contain a valid fmt chunk"


def test_ffmpeg_availability(engine):
    available, msg = engine.is_available()
    assert available is True
    assert "FFmpeg" in msg or "ffmpeg" in msg


def test_1_mp3_to_mmd_wav(engine, fixtures, tmp_path):
    """1. MP3 轉 MMD WAV 測試"""
    out_wav = tmp_path / "output_from_mp3.wav"
    ver = engine.convert_to_mmd_wav(fixtures["mp3"], out_wav)

    assert out_wav.exists()
    assert ver.is_valid is True
    assert ver.codec == "pcm_s16le"
    assert ver.sample_rate == 44100
    assert ver.channels == 2
    assert ver.bit_depth == 16
    assert ver.duration > 0

    verify_riff_wave_binary_header(out_wav)


def test_2_mp4_extract_audio_to_mmd_wav(engine, fixtures, tmp_path):
    """2. MP4 擷取音訊並轉 MMD WAV 測試"""
    out_wav = tmp_path / "output_from_mp4.wav"
    ver = engine.convert_to_mmd_wav(fixtures["mp4"], out_wav)

    assert out_wav.exists()
    assert ver.is_valid is True
    assert ver.codec == "pcm_s16le"
    assert ver.sample_rate == 44100
    assert ver.channels == 2

    info = engine.probe_media(out_wav)
    assert info.has_video is False, "Output WAV must not retain video stream"
    assert info.has_audio is True

    verify_riff_wave_binary_header(out_wav)


def test_3_flac_to_mmd_wav(engine, fixtures, tmp_path):
    """3. 96kHz 24-bit FLAC 轉 44.1kHz 16-bit MMD WAV 測試"""
    out_wav = tmp_path / "output_from_flac.wav"
    ver = engine.convert_to_mmd_wav(fixtures["flac"], out_wav)

    assert out_wav.exists()
    assert ver.is_valid is True
    assert ver.codec == "pcm_s16le"
    assert ver.sample_rate == 44100
    assert ver.channels == 2
    assert ver.bit_depth == 16

    verify_riff_wave_binary_header(out_wav)


def test_4_wav_to_mp3(engine, fixtures, tmp_path):
    """4. WAV 轉 MP3 320k 測試"""
    out_mp3 = tmp_path / "output_mp3.mp3"
    engine.convert_media(fixtures["mono_48k"], out_mp3, target_format="MP3", quality="320k")

    assert out_mp3.exists()
    info = engine.probe_media(out_mp3)
    assert info.has_audio is True
    assert info.audio_stream.codec_name == "mp3"


def test_5_different_sample_rates(engine, fixtures, tmp_path):
    """5. 不同採樣率 (22.05kHz -> 44.1kHz) 轉換測試"""
    out_wav = tmp_path / "output_upsampled.wav"
    ver = engine.convert_to_mmd_wav(fixtures["low_sr"], out_wav)

    assert ver.is_valid is True
    assert ver.sample_rate == 44100
    assert ver.channels == 2

    verify_riff_wave_binary_header(out_wav)


def test_6_mono_to_stereo(engine, fixtures, tmp_path):
    """6. 來源為 Mono 轉為 Stereo 雙聲道測試"""
    out_wav = tmp_path / "output_stereo.wav"
    ver = engine.convert_to_mmd_wav(fixtures["mono_48k"], out_wav, sample_rate=44100, channels=2)

    assert ver.is_valid is True
    assert ver.channels == 2
    assert ver.sample_rate == 44100

    verify_riff_wave_binary_header(out_wav)


def test_7_chinese_and_special_character_filename(engine, fixtures, tmp_path):
    """7. 中文檔名與特殊字元路徑處理測試"""
    out_wav = tmp_path / "【初音未來】輸出_MMD相容 (1) 特殊 #!@.wav"
    ver = engine.convert_to_mmd_wav(fixtures["chinese"], out_wav)

    assert out_wav.exists()
    assert ver.is_valid is True
    assert ver.codec == "pcm_s16le"

    verify_riff_wave_binary_header(out_wav)


def test_8_trimming_and_volume_gain(engine, fixtures, tmp_path):
    """8. 音訊時間裁切與音量增益測試"""
    out_wav = tmp_path / "output_trimmed.wav"
    ver = engine.convert_to_mmd_wav(
        fixtures["mp3"],
        out_wav,
        trim_start=0.5,
        trim_end=2.0,
        volume_gain_db=3.0
    )

    assert out_wav.exists()
    assert ver.is_valid is True
    # 2.0 - 0.5 = 1.5 seconds approx
    assert 1.3 <= ver.duration <= 1.7


def test_9_waveform_peaks_generation(engine, fixtures):
    """9. 音訊波形特徵點生成測試"""
    peaks = engine.get_waveform_peaks(fixtures["mp3"], num_points=100)
    assert len(peaks) == 100
    assert any(p > 0.0 for p in peaks), "Waveform peaks should not be completely zero"
    assert all(0.0 <= p <= 1.0 for p in peaks)


def test_10_corrupted_media_error_handling(engine, fixtures, tmp_path):
    """10. 損壞檔案的錯誤處理測試"""
    out_wav = tmp_path / "output_corrupted.wav"
    with pytest.raises(Exception):
        engine.convert_to_mmd_wav(fixtures["corrupted"], out_wav)
