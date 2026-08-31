"""The pipeline seam (AD-004): transcription + normalization as one swappable interface."""

from abc import ABC, abstractmethod

from x9ai.normalizer import Normalizer
from x9ai.transcriber import Transcriber


class Pipeline(ABC):
    """Single combined seam consumed by the HTTP layer."""

    @abstractmethod
    def process(self, audio: bytes, language: str) -> str:
        """Transcribe and normalize audio bytes into clean text."""


class StubPipeline(Pipeline):
    """Deterministic stand-in for contract tests; the real implementation lands in nlp-pipeline."""

    def process(self, audio: bytes, language: str) -> str:
        return f"stub:{language}:{len(audio)}"


class RealPipeline(Pipeline):
    """Composes a transcriber and a normalizer into the real processing pipeline."""

    def __init__(self, transcriber: Transcriber, normalizer: Normalizer) -> None:
        self._transcriber = transcriber
        self._normalizer = normalizer

    def process(self, audio: bytes, language: str) -> str:
        raw = self._transcriber.transcribe(audio, language)
        return self._normalizer.normalize(raw)