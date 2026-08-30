"""Runtime settings for the processing server."""

import os
from dataclasses import dataclass

MAX_AUDIO_BYTES_DEFAULT = 50 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    max_audio_bytes: int = MAX_AUDIO_BYTES_DEFAULT

    @classmethod
    def from_env(cls) -> "Settings":
        raw = os.environ.get("MAX_AUDIO_BYTES", "")
        try:
            value = int(raw)
        except ValueError:
            value = MAX_AUDIO_BYTES_DEFAULT
        return cls(max_audio_bytes=value)