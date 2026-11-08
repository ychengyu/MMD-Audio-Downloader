"""
Configuration management for MMD Audio Downloader.
Handles application settings persistence and default options.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class MMDWavConfig:
    sample_rate: int = 44100
    channels: int = 2
    bit_depth: int = 16
    volume_gain_db: float = 0.0
    remove_silence: bool = False
    normalize: bool = False


@dataclass
class AppConfig:
    output_dir: str = ""
    max_concurrent_tasks: int = 3
    theme_mode: str = "dark"      # "dark", "light", "system"
    accent_color: str = "#00D2B4"  # Default Miku Cyan/Teal
    theme: str = "dark"           # Kept for backward compatibility
    language: str = "zh_TW"
    preferred_format: str = "WAV" # "WAV", "MP3", "MP4", "FLAC", "M4A", "MKV"
    audio_format: str = "WAV"
    audio_quality: str = "best"   # "best", "320k", "256k", "192k", "128k"
    video_format: str = "MP4"
    video_quality: str = "best"   # "best", "2160", "1440", "1080", "720", "480", "360"
    video_codec: str = "h264"     # "h264", "copy"
    use_gpu_acceleration: bool = True  # Enable GPU hardware encoding if available
    gpu_backend: str = "auto"          # "auto", "nvenc", "qsv", "amf", "cpu"
    sidebar_collapsed: bool = False
    auto_open_folder: bool = False
    delete_intermediate_files: bool = True
    auto_retry_count: int = 2
    mmd_wav: MMDWavConfig = field(default_factory=MMDWavConfig)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        mmd_data = data.pop("mmd_wav", {})
        mmd_cfg = MMDWavConfig(**mmd_data) if isinstance(mmd_data, dict) else MMDWavConfig()
        # Backward compatibility for theme -> theme_mode
        if "theme" in data and "theme_mode" not in data:
            data["theme_mode"] = data["theme"]
        valid_keys = {k for k in cls.__dataclass_fields__.keys() if k != "mmd_wav"}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(mmd_wav=mmd_cfg, **filtered)


class ConfigManager:
    """Manages reading and writing application settings."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Path = None):
        if getattr(self, "_initialized", False):
            return

        if config_path is None:
            # Prefer %APPDATA%\MMD_Audio_Downloader\config.json
            appdata = os.environ.get("APPDATA")
            if appdata:
                config_dir = Path(appdata) / "MMD_Audio_Downloader"
            else:
                config_dir = Path.home() / ".mmd_audio_downloader"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "config.json"
        else:
            self.config_path = config_path

        self.config = self._load()
        self._initialized = True

    def _default_output_dir(self) -> str:
        """Default downloads directory: ~/Downloads/MMD_Audio"""
        downloads = Path.home() / "Downloads" / "MMD_Audio"
        downloads.mkdir(parents=True, exist_ok=True)
        return str(downloads)

    def _load(self) -> AppConfig:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = AppConfig.from_dict(data)
                if not cfg.output_dir:
                    cfg.output_dir = self._default_output_dir()
                return cfg
            except Exception as e:
                print(f"[Config] Error loading {self.config_path}: {e}, using defaults.")

        cfg = AppConfig()
        cfg.output_dir = self._default_output_dir()
        self.save(cfg)
        return cfg

    def save(self, config: AppConfig = None) -> None:
        if config is not None:
            self.config = config

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving {self.config_path}: {e}")

    def get(self) -> AppConfig:
        return self.config
