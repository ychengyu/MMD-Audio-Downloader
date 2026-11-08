"""
Audio Player Component with Waveform Integration for MMD Audio Downloader.
Uses PySide6.QtMultimedia for seamless playback and waveform synchronization.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg_engine import FFmpegEngine
from core.utils import format_time
from ui.components.waveform_widget import WaveformWidget


class AudioPlayerWidget(QFrame):
    """Audio preview player with playback controls and interactive waveform."""

    def __init__(self, ffmpeg_engine: Optional[FFmpegEngine] = None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.ffmpeg_engine = ffmpeg_engine or FFmpegEngine()

        self.current_file: Optional[Path] = None
        self.duration_secs: float = 0.0

        # Initialize Qt Multimedia Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Header: Title & Time display
        header_layout = QHBoxLayout()
        self.title_label = QLabel("未載入音訊")
        self.title_label.setStyleSheet("font-weight: bold; color: #E0E5EC;")
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #8C95A6; font-size: 12px;")
        header_layout.addWidget(self.title_label, 1)
        header_layout.addWidget(self.time_label, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header_layout)

        # Interactive Waveform
        self.waveform = WaveformWidget(self)
        main_layout.addWidget(self.waveform)

        # Controls Row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setMinimumWidth(80)
        self.play_btn.setEnabled(False)

        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setMinimumWidth(60)
        self.stop_btn.setEnabled(False)

        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.stop_btn)

        # Volume Controls
        controls_layout.addSpacing(16)
        vol_label = QLabel("音量")
        vol_label.setStyleSheet("color: #8C95A6; font-size: 11px;")
        controls_layout.addWidget(vol_label)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setMaximumWidth(120)
        controls_layout.addWidget(self.vol_slider)

        controls_layout.addStretch(1)
        main_layout.addLayout(controls_layout)

    def _connect_signals(self):
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn.clicked.connect(self.stop)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        # Player signals
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Waveform seek
        self.waveform.seek_requested.connect(self._on_waveform_seek)

    def load_audio(self, file_path: Path):
        """Load an audio file into the player and generate waveform peaks."""
        file_path = Path(file_path)
        if not file_path.exists():
            return

        self.stop()
        self.current_file = file_path
        self.title_label.setText(f"🎵 {file_path.name}")
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

        # Set media source
        self.player.setSource(QUrl.fromLocalFile(str(file_path)))

        # Extract waveform peaks asynchronously or fast via ffmpeg
        peaks = self.ffmpeg_engine.get_waveform_peaks(file_path, num_points=350)
        try:
            info = self.ffmpeg_engine.probe_media(file_path)
            self.duration_secs = info.duration
        except Exception:
            self.duration_secs = 0.0

        self.waveform.set_peaks(peaks, self.duration_secs)
        self.time_label.setText(f"00:00 / {format_time(self.duration_secs)}")

    def toggle_play(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.player.stop()
        self.waveform.set_playback_pos(0.0)
        self._update_time_label(0)

    def _on_volume_changed(self, val: int):
        self.audio_output.setVolume(val / 100.0)

    def _on_player_position_changed(self, pos_ms: int):
        dur_ms = self.player.duration()
        if dur_ms > 0:
            norm_pos = pos_ms / float(dur_ms)
            self.waveform.set_playback_pos(norm_pos)
        self._update_time_label(pos_ms)

    def _on_player_duration_changed(self, dur_ms: int):
        if dur_ms > 0:
            self.duration_secs = dur_ms / 1000.0
            self._update_time_label(self.player.position())

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸ 暫停")
        else:
            self.play_btn.setText("▶ 播放")

    def _on_waveform_seek(self, norm_pos: float):
        dur_ms = self.player.duration()
        if dur_ms > 0:
            seek_ms = int(norm_pos * dur_ms)
            self.player.setPosition(seek_ms)

    def _update_time_label(self, pos_ms: int):
        cur_sec = pos_ms / 1000.0
        self.time_label.setText(f"{format_time(cur_sec)} / {format_time(self.duration_secs)}")
