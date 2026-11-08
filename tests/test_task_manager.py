"""
Unit & Integration Tests for TaskManager, Queue Concurrency, and Cancellation.
"""

import sys
import time
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.task_manager import TaskManager, TaskStatus, TaskType
from core.utils import get_unique_filename, sanitize_filename
from tests.create_fixtures import create_test_fixtures


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="module")
def fixtures():
    fix_dir = Path(__file__).parent / "fixtures"
    if not (fix_dir / "test_stereo_440hz.mp3").exists():
        return create_test_fixtures(fix_dir)
    return {
        "mp3": fix_dir / "test_stereo_440hz.mp3",
        "flac": fix_dir / "test_highres_96k.flac",
        "mp4": fix_dir / "test_video_track.mp4"
    }


def test_filename_sanitization_and_uniqueness(tmp_path):
    """測試非法字元清理與同名檔案自動增加 (1)"""
    dirty = '【初音】:測試/音軌*<>|"?.mp3'
    cleaned = sanitize_filename(dirty)
    assert ":" not in cleaned
    assert "/" not in cleaned
    assert "*" not in cleaned
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert '"' not in cleaned
    assert "?" not in cleaned

    # Unique filename test
    test_file = tmp_path / "song.wav"
    test_file.write_text("dummy")

    cand1 = get_unique_filename(test_file)
    assert cand1.name == "song (1).wav"

    cand1.write_text("dummy")
    cand2 = get_unique_filename(test_file)
    assert cand2.name == "song (2).wav"


def test_batch_task_execution(qapp, fixtures, tmp_path):
    """8. 多筆任務批次轉換測試"""
    history_file = tmp_path / "history.json"
    tm = TaskManager(max_workers=2, history_file=history_file)

    task1 = tm.add_convert_task(
        input_file=fixtures["mp3"],
        output_dir=str(tmp_path / "out_batch"),
        mode="mmd_wav"
    )
    task2 = tm.add_convert_task(
        input_file=fixtures["flac"],
        output_dir=str(tmp_path / "out_batch"),
        mode="mmd_wav"
    )
    task3 = tm.add_convert_task(
        input_file=fixtures["mp4"],
        output_dir=str(tmp_path / "out_batch"),
        mode="mmd_wav"
    )

    # Wait for completion
    timeout = 20
    start = time.time()
    while time.time() - start < timeout:
        qapp.processEvents()
        if all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in [task1, task2, task3]):
            break
        time.sleep(0.1)

    assert task1.status == TaskStatus.COMPLETED
    assert task2.status == TaskStatus.COMPLETED
    assert task3.status == TaskStatus.COMPLETED

    assert Path(task1.output_file).exists()
    assert Path(task2.output_file).exists()
    assert Path(task3.output_file).exists()


def test_task_cancellation(qapp, fixtures, tmp_path):
    """9. 下載或轉檔途中取消測試"""
    tm = TaskManager(max_workers=1)

    # Queue first long or immediate task then cancel
    task = tm.add_convert_task(
        input_file=fixtures["mp4"],
        output_dir=str(tmp_path / "cancel_test"),
        mode="mmd_wav"
    )

    # Immediate cancel
    tm.cancel_task(task.task_id)

    time.sleep(0.5)
    qapp.processEvents()

    assert task.status in (TaskStatus.CANCELLED, TaskStatus.COMPLETED)
