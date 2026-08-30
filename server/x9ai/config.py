"""Runtime settings for the processing server."""

import os
from dataclasses import dataclass

MAX_AUDIO_BYTES_DEFAULT = 50 * 1024 * 1024
WHISPER_MODEL_DEFAULT = "medium"
WHISPER_DEVICE_DEFAULT = "auto"
WHISPER_COMPUTE_TYPE_DEFAULT = "default"


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


@dataclass(frozen=True)
class Settings:
    max_audio_bytes: int = MAX_AUDIO_BYTES_DEFAULT
    whisper_model: str = WHISPER_MODEL_DEFAULT
    whisper_device: str = WHISPER_DEVICE_DEFAULT
    whisper_compute_type: str = WHISPER_COMPUTE_TYPE_DEFAULT

    @classmethod
    def from_env(cls) -> "Settings":
        raw = os.environ.get("MAX_AUDIO_BYTES", "")
        try:
            value = int(raw)
        except ValueError:
            value = MAX_AUDIO_BYTES_DEFAULT
        return cls(
            max_audio_bytes=value,
            whisper_model=_env_str("WHISPER_MODEL", WHISPER_MODEL_DEFAULT),
            whisper_device=_env_str("WHISPER_DEVICE", WHISPER_DEVICE_DEFAULT),
            whisper_compute_type=_env_str("WHISPER_COMPUTE_TYPE", WHISPER_COMPUTE_TYPE_DEFAULT),
        )