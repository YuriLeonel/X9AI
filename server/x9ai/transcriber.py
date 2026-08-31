"""Transcription seam (AD-011): faster-whisper, lazily imported.

Importing this module does NOT require faster-whisper. The model is loaded only on
the first `transcribe` call, so the package and `create_app` boot in lean envs. An
injectable `model_factory` lets deterministic gates exercise the wrapper without
downloading a Whisper model.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from io import BytesIO

from x9ai.config import Settings

ModelFactory = Callable[[Settings], object]


def _default_model_factory(settings: Settings) -> object:
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


class Transcriber(ABC):
    """Converts audio bytes into raw transcribed text."""

    @abstractmethod
    def transcribe(self, audio: bytes, language: str) -> str:
        """Return the raw subtitle-free text for the given audio."""


class WhisperTranscriber(Transcriber):
    """Transcribes via faster-whisper, loading the model lazily on first call."""

    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self._model_factory = model_factory or _default_model_factory

    @property
    def model_name(self) -> str:
        """The configured (or default) Whisper model name, for operator visibility."""
        return self.settings.whisper_model

    def transcribe(self, audio: bytes, language: str) -> str:
        model = self._model_factory(self.settings)
        segments, _info = model.transcribe(BytesIO(audio), language=language)
        texts = [getattr(segment, "text", "") for segment in segments]
        return " ".join(texts).strip()
