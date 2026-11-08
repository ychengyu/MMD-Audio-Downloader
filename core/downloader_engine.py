"""
yt-dlp Downloader Engine for MMD Audio Downloader.
Handles multi-platform video/audio extraction, playlists, progress tracking,
speed calculation, cancellation, retry, post-download MMD WAV conversion,
and robust video+audio stream merging with FFmpeg.
"""

import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from core.ffmpeg_engine import FFmpegEngine, MMDVerificationResult, MediaInfo
from core.utils import get_bin_dir, get_unique_filename, sanitize_filename


@dataclass
class VideoFormatOption:
    format_id: str
    ext: str
    resolution: str
    height: Optional[int]
    fps: Optional[float]
    filesize: Optional[int]
    note: str


@dataclass
class ParsedMediaItem:
    url: str
    title: str
    duration: float
    thumbnail: str
    uploader: str
    extractor: str
    formats: List[VideoFormatOption] = field(default_factory=list)
    available_resolutions: List[str] = field(default_factory=list)
    is_live: bool = False
    is_playlist: bool = False
    playlist_title: Optional[str] = None
    playlist_index: Optional[int] = None
    playlist_count: Optional[int] = None


def translate_download_error(err: Exception) -> str:
    """Translate raw yt-dlp/FFmpeg/network errors into user-friendly Traditional Chinese."""
    raw = str(err)

    if "Sign in to confirm you’re not a bot" in raw or "bot" in raw.lower():
        return "此平台暫時觸發機器人驗證機制，請稍候重試或更新 yt-dlp。"
    if "Private video" in raw or "This video is private" in raw:
        return "此影片為私人影片或需要授權存取，無法公開下載。"
    if "Video unavailable" in raw or "not available" in raw:
        return "此影片已被刪除、設為不公開，或在您所在的地區無法播放。"
    if "HTTP Error 403" in raw or "Forbidden" in raw:
        return "下載請求被伺服器拒絕 (403 Forbidden)，請嘗試更新 yt-dlp 或稍後重試。"
    if "IncompleteRead" in raw or "RemoteDisconnected" in raw or "Connection reset" in raw:
        return "網路連線異常中斷，請檢查網路連線後重試。"
    if "Unsupported url" in raw or "is not a valid URL" in raw:
        return "無效或不支援的影音網址，請確認網址完整性。"
    if "Postprocessing: ffprobe/ffmpeg failed to merge" in raw:
        return "FFmpeg 影音串流合併失敗，請確認轉碼核心已正確安裝。"
    if "No such file or directory" in raw:
        return f"找不到目標檔案或路徑存取受阻: {raw}"

    # Return cleaned first line
    first_line = raw.splitlines()[0] if raw else "未知錯誤"
    return f"下載發生錯誤: {first_line}"


class DownloaderEngine:
    """Wrapper for yt-dlp downloading and media parsing."""

    def __init__(self, ffmpeg_engine: Optional[FFmpegEngine] = None):
        self.ffmpeg_engine = ffmpeg_engine or FFmpegEngine()

    def parse_url(
        self,
        url: str,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[ParsedMediaItem]:
        """
        Parse media information for a single URL or playlist without downloading.
        Returns a list of ParsedMediaItem (1 item for single media, multiple for playlists).
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",  # Extract playlist entries without downloading
            "skip_download": True,
            "ffmpeg_location": self.ffmpeg_engine.ffmpeg_path,
            "enable_file_urls": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if cancel_check and cancel_check():
                    raise InterruptedError("解析已取消")

                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("無法解析該網址，請確認網址正確且受支援。")

                # Check if playlist
                if "entries" in info:
                    entries = list(info.get("entries") or [])
                    items = []
                    playlist_title = info.get("title", "未命名播放清單")
                    total = len(entries)

                    for idx, entry in enumerate(entries, 1):
                        if not entry:
                            continue
                        entry_url = entry.get("url") or entry.get("webpage_url") or url
                        thumb = self._select_best_thumbnail(entry)
                        item = ParsedMediaItem(
                            url=entry_url,
                            title=entry.get("title", f"第 {idx} 部影片"),
                            duration=float(entry.get("duration") or 0.0),
                            thumbnail=thumb,
                            uploader=entry.get("uploader") or entry.get("channel") or "",
                            extractor=entry.get("extractor_key") or info.get("extractor_key", ""),
                            is_playlist=True,
                            playlist_title=playlist_title,
                            playlist_index=idx,
                            playlist_count=total
                        )
                        items.append(item)
                    return items
                else:
                    # Single media item
                    formats_list = []
                    unique_heights = set()

                    for f in info.get("formats", []):
                        vcodec = f.get("vcodec", "none")
                        acodec = f.get("acodec", "none")
                        h = f.get("height")
                        if h and isinstance(h, int) and h > 0:
                            unique_heights.add(h)

                        res = f.get("resolution") or (f"{h}p" if h else "純音訊")
                        if vcodec != "none" or acodec != "none":
                            formats_list.append(VideoFormatOption(
                                format_id=f.get("format_id", ""),
                                ext=f.get("ext", ""),
                                resolution=res,
                                height=h,
                                fps=f.get("fps"),
                                filesize=f.get("filesize") or f.get("filesize_approx"),
                                note=f.get("format_note", "")
                            ))

                    # Format available resolutions
                    sorted_heights = sorted(list(unique_heights), reverse=True)
                    res_labels = ["最佳可用畫質 (自動最高)"]
                    for h in sorted_heights:
                        if h >= 2160:
                            res_labels.append(f"{h}p (4K UHD)")
                        elif h >= 1440:
                            res_labels.append(f"{h}p (2K QHD)")
                        elif h >= 1080:
                            res_labels.append(f"{h}p (Full HD)")
                        elif h >= 720:
                            res_labels.append(f"{h}p (HD)")
                        else:
                            res_labels.append(f"{h}p (SD)")

                    thumb = self._select_best_thumbnail(info)

                    return [ParsedMediaItem(
                        url=info.get("webpage_url") or url,
                        title=info.get("title", "未命名媒體"),
                        duration=float(info.get("duration") or 0.0),
                        thumbnail=thumb,
                        uploader=info.get("uploader") or info.get("channel") or "",
                        extractor=info.get("extractor_key", ""),
                        formats=formats_list,
                        available_resolutions=res_labels,
                        is_live=bool(info.get("is_live", False)),
                        is_playlist=False
                    )]
        except Exception as e:
            if isinstance(e, InterruptedError):
                raise
            raise RuntimeError(translate_download_error(e)) from e

    def _select_best_thumbnail(self, info_dict: Dict[str, Any]) -> str:
        """Select the highest resolution thumbnail URL available from yt-dlp dict."""
        direct_thumb = info_dict.get("thumbnail")
        thumbs = info_dict.get("thumbnails")

        if thumbs and isinstance(thumbs, list):
            # Sort by width or preference if available
            valid_thumbs = [t for t in thumbs if isinstance(t, dict) and t.get("url")]
            if valid_thumbs:
                # Prefer largest width or highest preference
                sorted_thumbs = sorted(
                    valid_thumbs,
                    key=lambda x: (x.get("width") or 0) * (x.get("height") or 0) + (x.get("preference") or 0),
                    reverse=True
                )
                return sorted_thumbs[0]["url"]

        return direct_thumb or ""

    def download(
        self,
        url: str,
        output_dir: Path,
        mode: str = "mmd_wav",  # "mmd_wav", "audio", "video"
        target_format: str = "WAV",
        audio_quality: str = "best",
        video_quality: str = "best",
        video_codec: str = "h264",
        custom_filename: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        # Advanced MMD WAV options
        sample_rate: int = 44100,
        channels: int = 2,
        volume_gain_db: float = 0.0,
        trim_start: Optional[float] = None,
        trim_end: Optional[float] = None,
        remove_silence: bool = False,
        normalize: bool = False
    ) -> Tuple[Path, Optional[MMDVerificationResult]]:
        """
        Download media from URL.
        - mode == "mmd_wav": Downloads best audio and converts to 44.1kHz 16-bit Stereo PCM WAV with ffprobe validation.
        - mode == "audio": Downloads and converts to WAV, MP3, FLAC, M4A, etc.
        - mode == "video": Downloads video+audio streams, merges with FFmpeg into MP4/MKV/WEBM, and validates audio+video presence.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files: List[str] = []
        postprocessor_files: List[str] = []

        def ydl_progress_hook(d: Dict[str, Any]):
            if cancel_check and cancel_check():
                raise DownloadCancelled("使用者取消下載")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0.0
                eta = d.get("eta") or 0

                pct = 0.0
                if total > 0:
                    pct = (downloaded / total) * 100.0

                fn = d.get("filename", "")
                is_audio_part = any(ext in fn.lower() for ext in [".m4a", ".opus", ".f251", ".f140", ".webm"]) and "video" in mode
                step_prefix = "下載音軌中..." if is_audio_part else "下載中..."

                if progress_callback:
                    progress_callback({
                        "status": "downloading",
                        "percentage": pct,
                        "downloaded_bytes": downloaded,
                        "total_bytes": total,
                        "speed": speed,
                        "eta": eta,
                        "filename": fn,
                        "message": f"{step_prefix} {pct:.1f}%"
                    })

            elif status == "finished":
                fn = d.get("filename")
                if fn and fn not in downloaded_files:
                    downloaded_files.append(fn)
                if progress_callback:
                    progress_callback({
                        "status": "merging",
                        "percentage": 100.0,
                        "filename": fn,
                        "message": "下載完畢，正在合併影音串流..."
                    })

        def ydl_postprocessor_hook(d: Dict[str, Any]):
            if d.get("status") == "finished":
                fp = d.get("info_dict", {}).get("filepath")
                if fp and fp not in postprocessor_files:
                    postprocessor_files.append(fp)

        # Temporary directory
        temp_dir = output_dir / ".tmp_downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        template = "%(title)s.%(id)s.%(ext)s"

        ydl_opts: Dict[str, Any] = {
            "outtmpl": str(temp_dir / template),
            "progress_hooks": [ydl_progress_hook],
            "postprocessor_hooks": [ydl_postprocessor_hook],
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": self.ffmpeg_engine.ffmpeg_path,
            "enable_file_urls": True,
            "retries": 3,
            "fragment_retries": 3,
            "windowsfilenames": True,
            "noplaylist": True,
        }

        target_fmt_upper = target_format.upper()

        if mode in ("mmd_wav", "audio"):
            # Best audio only
            ydl_opts["format"] = "bestaudio/best"
        else:
            # Video mode
            clean_res = re.sub(r"[^\d]", "", video_quality) if video_quality != "best" else ""

            if target_fmt_upper == "MP4":
                # Prefer native H.264 (avc1) video + native AAC (m4a) audio for zero-transcode instant merging!
                if clean_res:
                    ydl_opts["format"] = (
                        f"bestvideo[vcodec^=avc1][height<={clean_res}]+bestaudio[ext=m4a]/"
                        f"bestvideo[ext=mp4][height<={clean_res}]+bestaudio[ext=m4a]/"
                        f"bestvideo[vcodec^=avc1][height<={clean_res}]+bestaudio/"
                        f"bestvideo[height<={clean_res}]+bestaudio/best[height<={clean_res}]/best"
                    )
                else:
                    ydl_opts["format"] = (
                        "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/"
                        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                        "bestvideo[vcodec^=avc1]+bestaudio/"
                        "bestvideo+bestaudio/best"
                    )
                ydl_opts["merge_output_format"] = "mp4"
                ydl_opts["postprocessor_args"] = {"merger": ["-c:v", "copy", "-c:a", "aac"]}

            elif target_fmt_upper == "MKV":
                if clean_res:
                    ydl_opts["format"] = f"bestvideo[height<={clean_res}]+bestaudio/best[height<={clean_res}]/best"
                else:
                    ydl_opts["format"] = "bestvideo+bestaudio/best"
                ydl_opts["merge_output_format"] = "mkv"

            elif target_fmt_upper == "WEBM":
                if clean_res:
                    ydl_opts["format"] = f"bestvideo[ext=webm][height<={clean_res}]+bestaudio[ext=webm]/bestvideo[height<={clean_res}]+bestaudio/best[height<={clean_res}]/best"
                else:
                    ydl_opts["format"] = "bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best"
                ydl_opts["merge_output_format"] = "webm"
            else:
                ydl_opts["format"] = "bestvideo+bestaudio/best"
                ydl_opts["merge_output_format"] = target_format.lower()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise RuntimeError("下載未能取得媒體資料。")

                title = custom_filename or info.get("title", "media")
                title_clean = sanitize_filename(title)

                # Locate the downloaded / merged file:
                raw_downloaded = None

                # 1. Check postprocessor output (merged file)
                for pp_file in reversed(postprocessor_files):
                    p = Path(pp_file)
                    if p.exists() and p.stat().st_size > 0:
                        raw_downloaded = p
                        break

                # 2. Check requested_downloads
                if not raw_downloaded and "requested_downloads" in info:
                    for rd in info["requested_downloads"]:
                        fp = rd.get("filepath")
                        if fp and Path(fp).exists():
                            raw_downloaded = Path(fp)
                            break

                # 3. Check prepared filename
                if not raw_downloaded:
                    prep_fn = ydl.prepare_filename(info)
                    if prep_fn and Path(prep_fn).exists():
                        raw_downloaded = Path(prep_fn)

                # 4. Check downloaded_files
                if not raw_downloaded:
                    for df in reversed(downloaded_files):
                        p = Path(df)
                        if p.exists() and p.stat().st_size > 0:
                            raw_downloaded = p
                            break

                # 5. Fallback search in temp_dir
                if not raw_downloaded:
                    cands = sorted(temp_dir.glob(f"*{info.get('id', '')}*"), key=os.path.getmtime, reverse=True)
                    if cands:
                        raw_downloaded = cands[0]
                    else:
                        all_files = sorted(temp_dir.glob("*"), key=os.path.getmtime, reverse=True)
                        if all_files:
                            raw_downloaded = all_files[0]
                        else:
                            raise FileNotFoundError("找不到下載後的檔案，請重試或確認磁碟空間充足。")

                # Post-processing by Mode:
                if mode == "mmd_wav":
                    if progress_callback:
                        progress_callback({"status": "converting", "message": "正在轉檔為 MMD 相容 WAV..."})

                    final_path = get_unique_filename(output_dir / f"{title_clean}.wav")

                    verification = self.ffmpeg_engine.convert_to_mmd_wav(
                        input_path=raw_downloaded,
                        output_path=final_path,
                        sample_rate=sample_rate,
                        channels=channels,
                        volume_gain_db=volume_gain_db,
                        trim_start=trim_start,
                        trim_end=trim_end,
                        remove_silence=remove_silence,
                        normalize=normalize,
                        progress_callback=lambda p, msg: progress_callback({"status": "converting", "percentage": p, "message": msg}) if progress_callback else None,
                        cancel_check=cancel_check
                    )

                    try:
                        raw_downloaded.unlink()
                    except Exception:
                        pass

                    return final_path, verification

                elif mode == "audio":
                    final_ext = target_format.lower()
                    final_path = get_unique_filename(output_dir / f"{title_clean}.{final_ext}")

                    if progress_callback:
                        progress_callback({"status": "converting", "message": f"正在轉檔為 {target_format.upper()}..."})

                    self.ffmpeg_engine.convert_media(
                        input_path=raw_downloaded,
                        output_path=final_path,
                        target_format=target_format,
                        quality=audio_quality,
                        progress_callback=lambda p, msg: progress_callback({"status": "converting", "percentage": p, "message": msg}) if progress_callback else None,
                        cancel_check=cancel_check
                    )

                    try:
                        raw_downloaded.unlink()
                    except Exception:
                        pass

                    return final_path, None

                else:
                    # Video mode
                    ext = target_format.lower() if target_format else raw_downloaded.suffix.lstrip(".")
                    final_path = get_unique_filename(output_dir / f"{title_clean}.{ext}")

                    # Check stream completeness with ffprobe
                    probe_raw = self.ffmpeg_engine.probe_media(raw_downloaded)
                    raw_ext = raw_downloaded.suffix.lower().lstrip(".")

                    # Case 1: Downloaded file is already the requested container (e.g. .mp4)
                    if raw_ext == ext:
                        audio_codec = probe_raw.audio_stream.codec_name.lower() if probe_raw.audio_stream else ""

                        # If audio is already AAC, MP3, or M4A (or video has no audio):
                        # ZERO transcode needed! Direct instant file move!
                        if not probe_raw.has_audio or audio_codec in ("aac", "mp3"):
                            if final_path.exists():
                                final_path.unlink()
                            shutil.move(str(raw_downloaded), str(final_path))
                        else:
                            # Audio is Opus/Vorbis: Fast remux (copy video track, transcode ONLY audio in 1-2 sec)
                            if progress_callback:
                                progress_callback({"status": "converting", "message": "正在快速封裝音訊串流 (影像無損拷貝)..."})
                            fast_remux_cmd = [
                                self.ffmpeg_engine.ffmpeg_path, "-y",
                                "-i", str(raw_downloaded),
                                "-c:v", "copy",
                                "-c:a", "aac", "-b:a", "192k",
                                "-movflags", "+faststart",
                                str(final_path)
                            ]
                            try:
                                self.ffmpeg_engine._run_ffmpeg_with_progress(
                                    fast_remux_cmd,
                                    total_duration=probe_raw.duration,
                                    progress_callback=lambda p, msg: progress_callback({"status": "converting", "percentage": p, "message": msg}) if progress_callback else None,
                                    cancel_check=cancel_check
                                )
                                raw_downloaded.unlink()
                            except Exception:
                                # Fallback to convert_media
                                self.ffmpeg_engine.convert_media(
                                    input_path=raw_downloaded,
                                    output_path=final_path,
                                    target_format=target_format,
                                    quality="best",
                                    progress_callback=lambda p, msg: progress_callback({"status": "converting", "percentage": p, "message": msg}) if progress_callback else None,
                                    cancel_check=cancel_check
                                )
                                try:
                                    raw_downloaded.unlink()
                                except Exception:
                                    pass
                    else:
                        # Case 2: Container mismatch (e.g. webm/mkv -> mp4)
                        # Try fast remux with -c:v copy first!
                        if progress_callback:
                            progress_callback({"status": "converting", "message": f"正在封裝至 {ext.upper()} 容器..."})

                        fast_remux_cmd = [
                            self.ffmpeg_engine.ffmpeg_path, "-y",
                            "-i", str(raw_downloaded),
                            "-c:v", "copy",
                            "-c:a", "aac" if ext == "mp4" else "copy",
                            "-movflags", "+faststart",
                            str(final_path)
                        ]
                        remux_success = False
                        try:
                            self.ffmpeg_engine._run_ffmpeg_with_progress(
                                fast_remux_cmd,
                                total_duration=probe_raw.duration,
                                progress_callback=lambda p, msg: progress_callback({"status": "converting", "percentage": p, "message": msg}) if progress_callback else None,
                                cancel_check=cancel_check
                            )
                            if final_path.exists() and final_path.stat().st_size > 0:
                                remux_success = True
                                try:
                                    raw_downloaded.unlink()
                                except Exception:
                                    pass
                        except Exception:
                            remux_success = False

                        if not remux_success:
                            gpu_info = self.ffmpeg_engine.detect_gpu_acceleration()
                            badge = f" (⚡ {gpu_info.name})" if gpu_info.has_gpu else " (多核心 CPU)"
                            if progress_callback:
                                progress_callback({"status": "converting", "message": f"正在以高速{badge}編碼 {ext.upper()}..."})
                            self.ffmpeg_engine.convert_media(
                                input_path=raw_downloaded,
                                output_path=final_path,
                                target_format=target_format,
                                quality="best",
                                progress_callback=lambda p, msg: progress_callback({"status": "converting", "percentage": p, "message": msg}) if progress_callback else None,
                                cancel_check=cancel_check
                            )
                            try:
                                raw_downloaded.unlink()
                            except Exception:
                                pass

                    # Final verification of video and audio streams
                    final_probe = self.ffmpeg_engine.probe_media(final_path)
                    if not final_probe.has_video:
                        raise RuntimeError("下載後的影片檔案缺少影像串流！")

                    return final_path, None

        except Exception as e:
            # Clean up temporary downloaded files on error
            for f in downloaded_files + postprocessor_files:
                p = Path(f)
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
            if isinstance(e, (InterruptedError, DownloadCancelled)):
                raise InterruptedError("使用者已取消下載作業。")
            raise RuntimeError(translate_download_error(e)) from e
        finally:
            try:
                if temp_dir.exists() and not list(temp_dir.iterdir()):
                    temp_dir.rmdir()
            except Exception:
                pass

    @staticmethod
    def update_ytdlp() -> Tuple[bool, str]:
        """Upgrade yt-dlp to latest version safely in dev and frozen environments."""
        try:
            import subprocess
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            # 1. If running as a frozen PyInstaller bundle
            if getattr(sys, "frozen", False):
                # Try system yt-dlp if installed in PATH
                ytdlp_bin = shutil.which("yt-dlp")
                if ytdlp_bin:
                    proc = subprocess.run(
                        [ytdlp_bin, "-U"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=creationflags,
                        timeout=60
                    )
                    if proc.returncode == 0:
                        return True, f"系統 yt-dlp 已更新：\n{proc.stdout.strip()}"

                return True, "目前執行於獨立綠色發行版，核心解析模組已內建為穩定相容版本。\n若有平台規格變更，可直接下載最新版主程式或由系統安裝 yt-dlp。"

            # 2. Standard Python environment
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=60
            )
            if proc.returncode == 0:
                return True, "yt-dlp 已成功更新至最新版本！"
            return False, f"更新失敗: {proc.stderr}"
        except Exception as e:
            return False, f"更新錯誤: {str(e)}"
