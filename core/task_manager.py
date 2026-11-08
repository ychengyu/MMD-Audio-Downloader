"""
Task Manager and Concurrent Worker Queue for MMD Audio Downloader.
Coordinates downloads, local conversions, progress reporting, retries,
cancellation, and task history persistence.
"""

import json
import os
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from core.downloader_engine import DownloaderEngine
from core.ffmpeg_engine import FFmpegEngine, MMDVerificationResult
from core.utils import format_bytes, format_speed, format_time, get_unique_filename, sanitize_filename


class TaskStatus(str, Enum):
    PENDING = "等候中"
    RUNNING = "執行中"
    COMPLETED = "已完成"
    FAILED = "失敗"
    CANCELLED = "已取消"


class TaskType(str, Enum):
    DOWNLOAD = "影音下載"
    CONVERT = "本機轉檔"


@dataclass
class TaskItem:
    task_id: str
    task_type: TaskType
    title: str
    source: str  # URL or source file path
    target_format: str = "WAV"
    mode: str = "mmd_wav"  # "mmd_wav", "audio", "video"
    output_dir: str = ""
    output_file: str = ""

    # Advanced options
    audio_quality: str = "best"
    video_quality: str = "best"
    sample_rate: int = 44100
    channels: int = 2
    volume_gain_db: float = 0.0
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    remove_silence: bool = False
    normalize: bool = False

    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    speed: float = 0.0
    eta: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    message: str = "等待排程..."
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 2

    # Verification details for MMD WAV
    is_mmd_valid: Optional[bool] = None
    verification_msg: str = ""
    media_details: Dict[str, str] = field(default_factory=dict)

    # Runtime cancellation control
    _is_cancelled: bool = False

    def cancel(self):
        self._is_cancelled = True
        self.status = TaskStatus.CANCELLED
        self.message = "已取消"

    def is_cancelled(self) -> bool:
        return self._is_cancelled


class TaskManagerSignals(QObject):
    task_added = Signal(str)  # task_id
    task_updated = Signal(str)  # task_id
    task_completed = Signal(str)  # task_id
    task_failed = Signal(str, str)  # task_id, error_msg
    task_cancelled = Signal(str)  # task_id
    queue_cleared = Signal()


class TaskManager:
    """Singleton-friendly Task Manager controlling background queue and worker threads."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_workers: int = 3, history_file: Optional[Path] = None):
        if getattr(self, "_initialized", False):
            return

        self.signals = TaskManagerSignals()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="MMDTaskWorker")
        self.tasks: Dict[str, TaskItem] = {}
        self.futures: Dict[str, Future] = {}
        self._lock = threading.RLock()

        self.ffmpeg_engine = FFmpegEngine()
        self.downloader_engine = DownloaderEngine(self.ffmpeg_engine)

        # Persistent history storage
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata) / "MMD_Audio_Downloader"
        else:
            base_dir = Path.home() / ".mmd_audio_downloader"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = history_file or (base_dir / "task_history.json")

        self._load_history()
        self._initialized = True

    def set_max_workers(self, count: int) -> None:
        count = max(1, min(10, count))
        if count != self.max_workers:
            self.max_workers = count
            with self._lock:
                self.executor.shutdown(wait=False, cancel_futures=False)
                self.executor = ThreadPoolExecutor(max_workers=count, thread_name_prefix="MMDTaskWorker")

    def add_download_task(
        self,
        url: str,
        output_dir: str,
        title: str = "",
        mode: str = "mmd_wav",
        target_format: str = "WAV",
        audio_quality: str = "best",
        video_quality: str = "best",
        sample_rate: int = 44100,
        channels: int = 2,
        volume_gain_db: float = 0.0,
        trim_start: Optional[float] = None,
        trim_end: Optional[float] = None,
        remove_silence: bool = False,
        normalize: bool = False
    ) -> TaskItem:
        task_id = str(uuid.uuid4())
        item = TaskItem(
            task_id=task_id,
            task_type=TaskType.DOWNLOAD,
            title=title or url,
            source=url,
            target_format=target_format,
            mode=mode,
            output_dir=output_dir,
            audio_quality=audio_quality,
            video_quality=video_quality,
            sample_rate=sample_rate,
            channels=channels,
            volume_gain_db=volume_gain_db,
            trim_start=trim_start,
            trim_end=trim_end,
            remove_silence=remove_silence,
            normalize=normalize
        )

        with self._lock:
            self.tasks[task_id] = item

        self.signals.task_added.emit(task_id)
        self._submit_task(item)
        return item

    def add_convert_task(
        self,
        input_file: Path,
        output_dir: str,
        mode: str = "mmd_wav",
        target_format: str = "WAV",
        audio_quality: str = "best",
        sample_rate: int = 44100,
        channels: int = 2,
        volume_gain_db: float = 0.0,
        trim_start: Optional[float] = None,
        trim_end: Optional[float] = None,
        remove_silence: bool = False,
        normalize: bool = False
    ) -> TaskItem:
        task_id = str(uuid.uuid4())
        item = TaskItem(
            task_id=task_id,
            task_type=TaskType.CONVERT,
            title=input_file.name,
            source=str(input_file),
            target_format=target_format,
            mode=mode,
            output_dir=output_dir,
            audio_quality=audio_quality,
            sample_rate=sample_rate,
            channels=channels,
            volume_gain_db=volume_gain_db,
            trim_start=trim_start,
            trim_end=trim_end,
            remove_silence=remove_silence,
            normalize=normalize
        )

        with self._lock:
            self.tasks[task_id] = item

        self.signals.task_added.emit(task_id)
        self._submit_task(item)
        return item

    def _submit_task(self, item: TaskItem) -> None:
        future = self.executor.submit(self._run_task_worker, item)
        with self._lock:
            self.futures[item.task_id] = future

    def _run_task_worker(self, item: TaskItem) -> None:
        if item.is_cancelled():
            return

        item.status = TaskStatus.RUNNING
        item.message = "開始處理..."
        self.signals.task_updated.emit(item.task_id)

        try:
            if item.task_type == TaskType.DOWNLOAD:
                self._execute_download(item)
            else:
                self._execute_conversion(item)

            if not item.is_cancelled():
                item.status = TaskStatus.COMPLETED
                item.progress = 100.0
                item.finished_at = time.time()
                item.message = "完成"
                self.signals.task_completed.emit(item.task_id)
                self._save_history()

        except InterruptedError:
            item.status = TaskStatus.CANCELLED
            item.message = "已被使用者取消"
            self.signals.task_cancelled.emit(item.task_id)

        except Exception as e:
            if item.is_cancelled():
                item.status = TaskStatus.CANCELLED
                item.message = "已取消"
                self.signals.task_cancelled.emit(item.task_id)
                return

            if item.retry_count < item.max_retries:
                item.retry_count += 1
                item.message = f"暫時失敗，即將重試 ({item.retry_count}/{item.max_retries})..."
                self.signals.task_updated.emit(item.task_id)
                for _ in range(10):
                    if item.is_cancelled():
                        item.status = TaskStatus.CANCELLED
                        item.message = "已取消"
                        self.signals.task_cancelled.emit(item.task_id)
                        return
                    time.sleep(0.2)
                self._submit_task(item)
                return

            item.status = TaskStatus.FAILED
            item.error_message = str(e)
            item.message = f"錯誤: {str(e)}"
            item.finished_at = time.time()
            self.signals.task_failed.emit(item.task_id, str(e))
            self._save_history()

    def _execute_download(self, item: TaskItem) -> None:
        def on_progress(p_info: Dict[str, Any]):
            if item.is_cancelled():
                raise InterruptedError("下載取消")

            status = p_info.get("status")
            if status == "downloading":
                item.progress = round(float(p_info.get("percentage", 0.0)), 1)
                item.speed = float(p_info.get("speed") or 0.0)
                item.eta = int(p_info.get("eta") or 0)
                item.downloaded_bytes = int(p_info.get("downloaded_bytes") or 0)
                item.total_bytes = int(p_info.get("total_bytes") or p_info.get("total_bytes_estimate") or 0)
                spd_str = format_speed(item.speed)
                eta_str = format_time(item.eta)
                item.message = f"下載中... {item.progress:.1f}% ({spd_str}, 剩餘 {eta_str})"
                self.signals.task_updated.emit(item.task_id)
            elif status in ("converting", "merging"):
                pct = p_info.get("percentage")
                if pct is not None:
                    item.progress = round(float(pct), 1)
                item.message = p_info.get("message", "處理中...")
                self.signals.task_updated.emit(item.task_id)

        output_path, verification = self.downloader_engine.download(
            url=item.source,
            output_dir=Path(item.output_dir),
            mode=item.mode,
            target_format=item.target_format,
            audio_quality=item.audio_quality,
            video_quality=item.video_quality,
            progress_callback=on_progress,
            cancel_check=item.is_cancelled,
            sample_rate=item.sample_rate,
            channels=item.channels,
            volume_gain_db=item.volume_gain_db,
            trim_start=item.trim_start,
            trim_end=item.trim_end,
            remove_silence=item.remove_silence,
            normalize=item.normalize
        )

        item.output_file = str(output_path)
        item.title = output_path.stem

        if verification:
            item.is_mmd_valid = verification.is_valid
            item.verification_msg = verification.message
            item.media_details = verification.details

    def _execute_conversion(self, item: TaskItem) -> None:
        input_file = Path(item.source)
        if not input_file.exists():
            raise FileNotFoundError(f"找不到來源檔案: {item.source}")

        output_dir = Path(item.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        def on_progress(pct: float, msg: str):
            if item.is_cancelled():
                raise InterruptedError("轉檔取消")
            item.progress = round(pct, 1)
            item.message = msg
            self.signals.task_updated.emit(item.task_id)

        title_clean = sanitize_filename(input_file.stem)

        if item.mode == "mmd_wav" or item.target_format.upper() == "WAV":
            target_path = get_unique_filename(output_dir / f"{title_clean}.wav")
            item.message = "正在進行 MMD WAV 轉檔..."
            self.signals.task_updated.emit(item.task_id)

            verification = self.ffmpeg_engine.convert_to_mmd_wav(
                input_path=input_file,
                output_path=target_path,
                sample_rate=item.sample_rate,
                channels=item.channels,
                volume_gain_db=item.volume_gain_db,
                trim_start=item.trim_start,
                trim_end=item.trim_end,
                remove_silence=item.remove_silence,
                normalize=item.normalize,
                progress_callback=on_progress,
                cancel_check=item.is_cancelled
            )

            item.output_file = str(target_path)
            item.is_mmd_valid = verification.is_valid
            item.verification_msg = verification.message
            item.media_details = verification.details

            if not verification.is_valid:
                raise RuntimeError(f"MMD WAV 驗證未通過: {verification.message}")
        else:
            ext = item.target_format.lower()
            target_path = get_unique_filename(output_dir / f"{title_clean}.{ext}")
            item.message = f"正在轉檔為 {item.target_format}..."
            self.signals.task_updated.emit(item.task_id)

            self.ffmpeg_engine.convert_media(
                input_path=input_file,
                output_path=target_path,
                target_format=item.target_format,
                quality=item.audio_quality,
                progress_callback=on_progress,
                cancel_check=item.is_cancelled
            )
            item.output_file = str(target_path)

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            task.cancel()
            future = self.futures.get(task_id)
            if future and not future.running():
                future.cancel()
        self.signals.task_cancelled.emit(task_id)
        return True

    def retry_task(self, task_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            task._is_cancelled = False
            task.status = TaskStatus.PENDING
            task.progress = 0.0
            task.message = "等待重新執行..."
            task.retry_count = 0
            self._submit_task(task)
        self.signals.task_updated.emit(task_id)
        return True

    def remove_task(self, task_id: str) -> None:
        with self._lock:
            if task_id in self.tasks:
                self.cancel_task(task_id)
                del self.tasks[task_id]
            if task_id in self.futures:
                del self.futures[task_id]
        self._save_history()

    def clear_completed(self) -> None:
        with self._lock:
            to_del = [tid for tid, t in self.tasks.items() if t.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)]
            for tid in to_del:
                del self.tasks[tid]
                if tid in self.futures:
                    del self.futures[tid]
        self.signals.queue_cleared.emit()
        self._save_history()

    def get_all_tasks(self) -> List[TaskItem]:
        with self._lock:
            return list(self.tasks.values())

    def _load_history(self) -> None:
        if not self.history_file.exists():
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            for r in records[-50:]:  # Keep up to 50 recent items
                tid = r.get("task_id", str(uuid.uuid4()))
                status_str = r.get("status", TaskStatus.COMPLETED.value)
                tt_str = r.get("task_type", TaskType.DOWNLOAD.value)

                item = TaskItem(
                    task_id=tid,
                    task_type=TaskType.CONVERT if "轉檔" in tt_str else TaskType.DOWNLOAD,
                    title=r.get("title", ""),
                    source=r.get("source", ""),
                    target_format=r.get("target_format", "WAV"),
                    mode=r.get("mode", "mmd_wav"),
                    output_dir=r.get("output_dir", ""),
                    output_file=r.get("output_file", ""),
                    status=TaskStatus.COMPLETED if status_str == TaskStatus.COMPLETED.value else TaskStatus.FAILED,
                    progress=100.0,
                    message=r.get("message", "歷史任務"),
                    created_at=r.get("created_at", time.time()),
                    finished_at=r.get("finished_at"),
                    is_mmd_valid=r.get("is_mmd_valid"),
                    verification_msg=r.get("verification_msg", ""),
                    media_details=r.get("media_details", {})
                )
                self.tasks[tid] = item
        except Exception as e:
            print(f"[TaskManager] Error loading history: {e}")

    def _save_history(self) -> None:
        try:
            records = []
            with self._lock:
                for t in self.tasks.values():
                    if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                        records.append({
                            "task_id": t.task_id,
                            "task_type": t.task_type.value,
                            "title": t.title,
                            "source": t.source,
                            "target_format": t.target_format,
                            "mode": t.mode,
                            "output_dir": t.output_dir,
                            "output_file": t.output_file,
                            "status": t.status.value,
                            "message": t.message,
                            "created_at": t.created_at,
                            "finished_at": t.finished_at,
                            "is_mmd_valid": t.is_mmd_valid,
                            "verification_msg": t.verification_msg,
                            "media_details": t.media_details
                        })
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(records[-100:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[TaskManager] Error saving history: {e}")
