"""
FFmpeg and ffprobe engine for MMD Audio Downloader.
Handles media probing, MMD-compliant WAV conversion, generic audio/video conversion,
audio extraction, waveform generation, and strict ffprobe verification.
"""

import collections
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.utils import get_bin_dir, parse_time_to_seconds


@dataclass
class StreamInfo:
    codec_name: str = ""
    codec_type: str = ""  # "audio" or "video"
    sample_rate: int = 0
    channels: int = 0
    channel_layout: str = ""
    bits_per_sample: int = 0
    bit_rate: int = 0
    width: int = 0
    height: int = 0
    fps: float = 0.0


@dataclass
class MediaInfo:
    file_path: str = ""
    format_name: str = ""
    duration: float = 0.0
    size_bytes: int = 0
    bit_rate: int = 0
    has_audio: bool = False
    has_video: bool = False
    audio_stream: Optional[StreamInfo] = None
    video_stream: Optional[StreamInfo] = None
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def display_duration(self) -> str:
        from core.utils import format_time
        return format_time(self.duration)

    @property
    def display_size(self) -> str:
        from core.utils import format_bytes
        return format_bytes(self.size_bytes)


@dataclass
class MMDVerificationResult:
    is_valid: bool
    codec: str
    sample_rate: int
    channels: int
    bit_depth: int
    duration: float
    format_name: str
    message: str
    details: Dict[str, str] = field(default_factory=dict)


@dataclass
class GPUInfo:
    has_gpu: bool = False
    backend: str = "cpu"            # "nvenc", "qsv", "amf", "cpu"
    name: str = "CPU 軟體編碼"       # e.g. "NVIDIA NVENC 顯卡硬體加速 (⚡ 極速)"
    h264_encoder: str = "libx264"
    hevc_encoder: str = "libx265"
    extra_flags: List[str] = field(default_factory=list)
    hwaccel_flags: List[str] = field(default_factory=list)
    details: str = ""


class FFmpegEngine:
    """Core engine for all FFmpeg / ffprobe operations."""

    def __init__(self, custom_ffmpeg: Optional[str] = None, custom_ffprobe: Optional[str] = None):
        self.ffmpeg_path = self._find_binary("ffmpeg", custom_ffmpeg)
        self.ffprobe_path = self._find_binary("ffprobe", custom_ffprobe)
        self._cached_gpu_info: Optional[GPUInfo] = None

    def detect_gpu_acceleration(self, force_refresh: bool = False) -> GPUInfo:
        """
        Detect and verify working GPU hardware video encoders on the system:
        - NVIDIA NVENC (h264_nvenc)
        - Intel QuickSync (h264_qsv)
        - AMD AMF (h264_amf)
        Falls back cleanly to CPU (libx264) if no GPU is available or if disabled in config.
        """
        if self._cached_gpu_info is not None and not force_refresh:
            return self._cached_gpu_info

        from core.config import ConfigManager
        cfg = ConfigManager().get()
        if not getattr(cfg, "use_gpu_acceleration", True):
            self._cached_gpu_info = GPUInfo(
                has_gpu=False,
                backend="cpu",
                name="CPU 多核心編碼 (使用者手動停用顯卡)",
                h264_encoder="libx264",
                hevc_encoder="libx265",
                extra_flags=["-preset", "veryfast", "-threads", "0", "-pix_fmt", "yuv420p"],
                details="依使用者設定採用多核心 CPU 進行編碼"
            )
            return self._cached_gpu_info

        preferred_backend = getattr(cfg, "gpu_backend", "auto")

        candidates = [
            ("nvenc", "h264_nvenc", "hevc_nvenc", "NVIDIA NVENC 顯卡硬體加速 (⚡ 極速)",
             ["-preset", "p4", "-tune", "hq", "-b:v", "0", "-cq", "23", "-pix_fmt", "yuv420p"],
             ["-hwaccel", "cuda"]),
            ("qsv", "h264_qsv", "hevc_qsv", "Intel QuickSync 顯卡硬體加速 (⚡ 極速)",
             ["-preset", "veryfast", "-global_quality", "23"],
             ["-hwaccel", "qsv"]),
            ("amf", "h264_amf", "hevc_amf", "AMD AMF 顯卡硬體加速 (⚡ 極速)",
             ["-quality", "speed", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23", "-pix_fmt", "yuv420p"],
             ["-hwaccel", "d3d11va"]),
        ]

        if preferred_backend in ("nvenc", "qsv", "amf"):
            candidates.sort(key=lambda x: 0 if x[0] == preferred_backend else 1)
        elif preferred_backend == "cpu":
            candidates = []

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        for backend_id, h264_enc, hevc_enc, display_name, flags, hw_flags in candidates:
            try:
                test_cmd = [
                    self.ffmpeg_path, "-y",
                    "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.04",
                    "-c:v", h264_enc,
                    "-f", "null", "-"
                ]
                res = subprocess.run(
                    test_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=2.5,
                    creationflags=creationflags
                )
                if res.returncode == 0:
                    self._cached_gpu_info = GPUInfo(
                        has_gpu=True,
                        backend=backend_id,
                        name=display_name,
                        h264_encoder=h264_enc,
                        hevc_encoder=hevc_enc,
                        extra_flags=flags,
                        hwaccel_flags=hw_flags,
                        details=f"已成功啟用 {display_name}，視訊編碼速度提升高達 20~50 倍且不佔用 CPU。"
                    )
                    return self._cached_gpu_info
            except Exception:
                continue

        # Fallback to multi-threaded CPU
        self._cached_gpu_info = GPUInfo(
            has_gpu=False,
            backend="cpu",
            name="CPU 多核心編碼",
            h264_encoder="libx264",
            hevc_encoder="libx265",
            extra_flags=["-preset", "veryfast", "-threads", "0", "-pix_fmt", "yuv420p"],
            details="未檢測到相容之獨立顯卡硬體編碼器，自動啟用多核心 CPU 高速編碼模式。"
        )
        return self._cached_gpu_info

    def _find_binary(self, name: str, custom_path: Optional[str] = None) -> str:
        """Find the binary path prioritizing local bin/ folder, then system PATH."""
        exe_name = f"{name}.exe" if sys.platform == "win32" else name

        if custom_path and os.path.exists(custom_path):
            return custom_path

        # 1. Check local bin/ dir
        bin_dir = get_bin_dir()
        candidate = bin_dir / exe_name
        if candidate.is_file():
            return str(candidate)

        # 2. Check current working dir / bin
        local_cand = Path.cwd() / "bin" / exe_name
        if local_cand.is_file():
            return str(local_cand)

        # 3. Check system PATH
        path_binary = shutil.which(name)
        if path_binary:
            return path_binary

        # 4. Check common WinGet links on Windows
        winget_path = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name
        if winget_path.is_file():
            return str(winget_path)

        return exe_name  # Fallback to plain name

    def is_available(self) -> Tuple[bool, str]:
        """Check if both ffmpeg and ffprobe are available and operational."""
        try:
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            p1 = subprocess.run(
                [self.ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=5
            )
            p2 = subprocess.run(
                [self.ffprobe_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=5
            )
            if p1.returncode == 0 and p2.returncode == 0:
                first_line = p1.stdout.splitlines()[0] if p1.stdout else "FFmpeg ready"
                return True, first_line
            return False, f"FFmpeg returned code {p1.returncode}, ffprobe returned code {p2.returncode}"
        except Exception as e:
            return False, f"無法啟動 FFmpeg: {str(e)}"

    def probe_media(self, file_path: Path) -> MediaInfo:
        """
        Probe a media file using ffprobe and return parsed MediaInfo.
        Raises RuntimeError on failure.
        """
        path_str = str(file_path)
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"找不到檔案: {path_str}")

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path_str
        ]

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            timeout=15
        )

        if res.returncode != 0:
            raise RuntimeError(f"ffprobe 解析失敗: {res.stderr.strip()}")

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"無法解析 ffprobe JSON 輸出: {e}")

        format_data = data.get("format", {})
        streams_data = data.get("streams", [])

        media_info = MediaInfo(
            file_path=path_str,
            format_name=format_data.get("format_name", ""),
            duration=float(format_data.get("duration", 0.0) or 0.0),
            size_bytes=int(format_data.get("size", 0) or os.path.getsize(path_str)),
            bit_rate=int(format_data.get("bit_rate", 0) or 0),
            tags=format_data.get("tags", {})
        )

        for s in streams_data:
            codec_type = s.get("codec_type")
            codec_name = s.get("codec_name", "")

            if codec_type == "audio" and not media_info.has_audio:
                media_info.has_audio = True
                sr = int(s.get("sample_rate", 0) or 0)
                ch = int(s.get("channels", 0) or 0)
                br = int(s.get("bit_rate", 0) or 0)
                bits = int(s.get("bits_per_sample", 0) or s.get("bits_per_raw_sample", 0) or 0)

                media_info.audio_stream = StreamInfo(
                    codec_name=codec_name,
                    codec_type="audio",
                    sample_rate=sr,
                    channels=ch,
                    channel_layout=s.get("channel_layout", ""),
                    bits_per_sample=bits,
                    bit_rate=br
                )
            elif codec_type == "video" and not media_info.has_video:
                # Discard attached pictures (cover art) if tagged as attached_pic
                if s.get("disposition", {}).get("attached_pic", 0) == 1:
                    continue
                media_info.has_video = True
                w = int(s.get("width", 0) or 0)
                h = int(s.get("height", 0) or 0)
                # Compute fps
                r_frame_rate = s.get("r_frame_rate", "0/1")
                fps = 0.0
                try:
                    num, den = r_frame_rate.split("/")
                    fps = float(num) / float(den) if float(den) != 0 else 0.0
                except Exception:
                    pass

                media_info.video_stream = StreamInfo(
                    codec_name=codec_name,
                    codec_type="video",
                    width=w,
                    height=h,
                    fps=round(fps, 2)
                )

        return media_info

    def convert_to_mmd_wav(
        self,
        input_path: Path,
        output_path: Path,
        sample_rate: int = 44100,
        channels: int = 2,
        volume_gain_db: float = 0.0,
        trim_start: Optional[float] = None,
        trim_end: Optional[float] = None,
        remove_silence: bool = False,
        normalize: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> MMDVerificationResult:
        """
        Convert any audio or video file to a strict MMD-compliant WAV:
        - RIFF/WAVE container
        - Linear PCM 16-bit Signed (pcm_s16le)
        - 44,100 Hz (or specified)
        - Stereo (2 channels, or specified)
        - Verification via ffprobe.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output_path.with_suffix(".tmp.wav")

        # Probe duration for progress computation
        total_duration = 0.0
        try:
            info = self.probe_media(input_path)
            total_duration = info.duration
        except Exception:
            pass

        # Build FFmpeg command
        cmd = [self.ffmpeg_path, "-y"]

        # Trimming start (fast seek before input)
        if trim_start is not None and trim_start > 0:
            cmd.extend(["-ss", f"{trim_start:.3f}"])

        cmd.extend(["-i", str(input_path)])

        # Trimming end (duration or timestamp)
        if trim_end is not None and trim_end > (trim_start or 0):
            duration_to_cut = trim_end - (trim_start or 0)
            cmd.extend(["-t", f"{duration_to_cut:.3f}"])
            total_duration = duration_to_cut

        # Audio filters list
        af_filters = []
        if volume_gain_db != 0.0:
            af_filters.append(f"volume={volume_gain_db:.1f}dB")

        if remove_silence:
            # Removes silence at beginning and end, and trims long silence in middle
            af_filters.append("silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB:stop_periods=1:stop_duration=0.5:stop_threshold=-50dB")

        if normalize:
            af_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        if af_filters:
            cmd.extend(["-af", ",".join(af_filters)])

        # MMD Standard WAV Specifications:
        # -vn: discard video
        # -c:a pcm_s16le: 16-bit signed PCM
        # -ar: sample rate (44100 Hz)
        # -ac: channels (2 for Stereo)
        # -f wav: RIFF/WAVE format
        cmd.extend([
            "-vn",
            "-c:a", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-f", "wav",
            str(temp_output)
        ])

        # Execute conversion and monitor progress
        self._run_ffmpeg_with_progress(
            cmd,
            total_duration=total_duration,
            progress_callback=progress_callback,
            cancel_check=cancel_check
        )

        # Move temp to final output (Cross-filesystem safe)
        if temp_output.exists():
            if output_path.exists():
                output_path.unlink()
            shutil.move(str(temp_output), str(output_path))
        else:
            raise RuntimeError("FFmpeg 轉檔未產生輸出檔案。")

        # Verify output via ffprobe
        verification = self.verify_mmd_wav(
            output_path,
            expected_sr=sample_rate,
            expected_ch=channels,
            expected_bits=16
        )

        return verification

    def verify_mmd_wav(
        self,
        wav_path: Path,
        expected_sr: int = 44100,
        expected_ch: int = 2,
        expected_bits: int = 16
    ) -> MMDVerificationResult:
        """
        Verify that a WAV file conforms strictly to MMD standards:
        - Format is WAV (RIFF/WAVE)
        - Codec is pcm_s16le
        - Sample rate matches expected (default 44100 Hz)
        - Channels match expected (default 2)
        - Bit depth is 16-bit
        """
        try:
            info = self.probe_media(wav_path)
        except Exception as e:
            return MMDVerificationResult(
                is_valid=False,
                codec="unknown",
                sample_rate=0,
                channels=0,
                bit_depth=0,
                duration=0.0,
                format_name="",
                message=f"無法以 ffprobe 讀取檔案: {str(e)}"
            )

        if not info.has_audio or not info.audio_stream:
            return MMDVerificationResult(
                is_valid=False,
                codec="none",
                sample_rate=0,
                channels=0,
                bit_depth=0,
                duration=0.0,
                format_name=info.format_name,
                message="檔案中未檢測到有效音軌。"
            )

        astream = info.audio_stream
        issues = []

        # 1. Format check: format_name should contain "wav"
        if "wav" not in info.format_name.lower():
            issues.append(f"容器格式不是標準 WAV (檢測為: {info.format_name})")

        # 2. Codec check: must be pcm_s16le
        if astream.codec_name.lower() != "pcm_s16le":
            issues.append(f"音訊編碼不是 16-bit PCM (檢測為: {astream.codec_name})，MMD 可能無法解碼！")

        # 3. Sample rate check
        if astream.sample_rate != expected_sr:
            issues.append(f"採樣率不符合 (檢測為: {astream.sample_rate} Hz，預期: {expected_sr} Hz)")

        # 4. Channels check
        if astream.channels != expected_ch:
            issues.append(f"聲道數不符合 (檢測為: {astream.channels} 聲道，預期: {expected_ch} 聲道)")

        # 5. Duration check
        if info.duration <= 0:
            issues.append("音訊時長為 0 秒或無效。")

        # Determine bit depth
        bit_depth = astream.bits_per_sample or (16 if astream.codec_name == "pcm_s16le" else 0)

        details = {
            "格式容器": info.format_name,
            "音訊編碼": astream.codec_name,
            "採樣率": f"{astream.sample_rate} Hz",
            "聲道數": f"{astream.channels} ({'Stereo 雙聲道' if astream.channels == 2 else 'Mono 單聲道'})",
            "位元深度": f"{bit_depth}-bit",
            "音訊時長": info.display_duration,
            "檔案大小": info.display_size
        }

        if issues:
            return MMDVerificationResult(
                is_valid=False,
                codec=astream.codec_name,
                sample_rate=astream.sample_rate,
                channels=astream.channels,
                bit_depth=bit_depth,
                duration=info.duration,
                format_name=info.format_name,
                message="；".join(issues),
                details=details
            )

        return MMDVerificationResult(
            is_valid=True,
            codec=astream.codec_name,
            sample_rate=astream.sample_rate,
            channels=astream.channels,
            bit_depth=bit_depth,
            duration=info.duration,
            format_name=info.format_name,
            message="完美符合 MMD 相容標準 (16-bit Signed PCM, 44.1 kHz, Stereo WAV)",
            details=details
        )

    def convert_media(
        self,
        input_path: Path,
        output_path: Path,
        target_format: str,
        quality: str = "best",
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Path:
        """
        Generic audio and video conversion.
        Formats supported:
          Audio: WAV, MP3, FLAC, M4A, AAC, OGG, OPUS
          Video: MP4, MKV, WEBM, MOV
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output_path.with_suffix(f".tmp{output_path.suffix}")

        fmt = target_format.upper()
        audio_only_formats = {"WAV", "MP3", "FLAC", "M4A", "AAC", "OGG", "OPUS"}

        # Probe duration for progress
        total_duration = 0.0
        try:
            info = self.probe_media(input_path)
            total_duration = info.duration
        except Exception:
            pass

        used_gpu = False
        cmd = [self.ffmpeg_path, "-y"]

        if fmt not in audio_only_formats:
            gpu_info = self.detect_gpu_acceleration()
            if gpu_info.has_gpu and gpu_info.hwaccel_flags:
                cmd.extend(gpu_info.hwaccel_flags)

        cmd.extend(["-i", str(input_path)])
        if fmt in audio_only_formats:
            cmd.append("-vn")  # Discard video
            if fmt == "WAV":
                cmd.extend(["-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2"])
            elif fmt == "MP3":
                bitrate_map = {"best": "320k", "320k": "320k", "192k": "192k", "128k": "128k"}
                br = bitrate_map.get(quality.lower(), "320k")
                cmd.extend(["-c:a", "libmp3lame", "-b:a", br])
            elif fmt == "FLAC":
                cmd.extend(["-c:a", "flac"])
            elif fmt in ("M4A", "AAC"):
                cmd.extend(["-c:a", "aac", "-b:a", "256k"])
            elif fmt == "OGG":
                cmd.extend(["-c:a", "libvorbis", "-q:a", "6"])
            elif fmt == "OPUS":
                cmd.extend(["-c:a", "libopus", "-b:a", "160k"])
        else:
            # Video container output
            if fmt in ("MP4", "MOV"):
                gpu_info = self.detect_gpu_acceleration()
                if gpu_info.has_gpu and gpu_info.h264_encoder != "libx264":
                    cmd.extend(["-c:v", gpu_info.h264_encoder])
                    cmd.extend(gpu_info.extra_flags)
                    cmd.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"])
                    used_gpu = True
                else:
                    cmd.extend([
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-threads", "0",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart"
                    ])
            elif fmt == "MKV":
                cmd.extend(["-c:v", "copy", "-c:a", "copy"])
            elif fmt == "WEBM":
                cmd.extend(["-c:v", "libvpx-vp9", "-c:a", "libopus"])

        cmd.append(str(temp_output))

        try:
            self._run_ffmpeg_with_progress(
                cmd,
                total_duration=total_duration,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
        except Exception as e:
            if used_gpu and not (cancel_check and cancel_check()):
                temp_output.unlink(missing_ok=True)
                cpu_cmd = [self.ffmpeg_path, "-y", "-i", str(input_path)]
                cpu_cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-threads", "0",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    str(temp_output)
                ])
                self._run_ffmpeg_with_progress(
                    cpu_cmd,
                    total_duration=total_duration,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            else:
                raise

        if temp_output.exists():
            if output_path.exists():
                output_path.unlink()
            shutil.move(str(temp_output), str(output_path))
            return output_path
        else:
            raise RuntimeError(f"轉檔失敗，未產生目標檔案: {output_path.name}")

    def get_waveform_peaks(self, file_path: Path, num_points: int = 300) -> List[float]:
        """
        Extract normalized peak amplitudes (0.0 to 1.0) across the file for waveform visualization.
        Uses ffmpeg to downsample audio to mono 8kHz raw 8-bit unsigned PCM for ultra-fast reading.
        """
        try:
            cmd = [
                self.ffmpeg_path,
                "-v", "quiet",
                "-i", str(file_path),
                "-ac", "1",
                "-ar", "8000",
                "-f", "u8",
                "-"
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                timeout=10
            )
            raw_bytes = proc.stdout
            if not raw_bytes:
                return [0.0] * num_points

            total_samples = len(raw_bytes)
            chunk_size = max(1, total_samples // num_points)
            peaks = []

            for i in range(num_points):
                start = i * chunk_size
                end = min(total_samples, start + chunk_size)
                if start >= total_samples:
                    peaks.append(0.0)
                    continue
                chunk = raw_bytes[start:end]
                # Samples are 0-255 with 128 as silence
                max_dev = max(abs(b - 128) for b in chunk)
                norm_peak = min(1.0, max_dev / 128.0)
                peaks.append(round(norm_peak, 3))

            return peaks
        except Exception as e:
            print(f"[FFmpegEngine] get_waveform_peaks failed: {e}")
            return [0.0] * num_points

    def _run_ffmpeg_with_progress(
        self,
        cmd: List[str],
        total_duration: float,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> None:
        """Execute FFmpeg process while parsing time progression and supporting cancellation."""
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        # We tell ffmpeg to output progress to stderr
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags
        )

        time_pattern = re.compile(r"time=(\d+:\d+:\d+\.\d+|\d+\.\d+)")
        last_pct = 0.0
        stderr_history = collections.deque(maxlen=40)

        try:
            while True:
                if cancel_check and cancel_check():
                    proc.kill()
                    proc.wait()
                    raise InterruptedError("轉檔已被使用者取消。")

                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break

                if line:
                    stderr_history.append(line)
                    if progress_callback and total_duration > 0:
                        match = time_pattern.search(line)
                        if match:
                            time_str = match.group(1)
                            current_secs = parse_time_to_seconds(time_str)
                            if current_secs is not None:
                                pct = min(99.0, (current_secs / total_duration) * 100.0)
                                if pct > last_pct:
                                    last_pct = pct
                                    progress_callback(pct, f"轉檔中... {pct:.1f}%")

            returncode = proc.wait()
            if returncode != 0:
                # Capture remaining stderr if any
                remaining = proc.stderr.read()
                if remaining:
                    stderr_history.extend(remaining.splitlines())
                error_summary = "".join(stderr_history)[-600:].strip()
                raise RuntimeError(f"FFmpeg 執行錯誤 (代碼 {returncode}):\n{error_summary}")

            if progress_callback:
                progress_callback(100.0, "轉檔完成")

        except Exception:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            raise
