"""The pipeline seam (AD-004): transcription + normalization as one swappable interface."""

from abc import ABC, abstractmethod


class Pipeline(ABC):
    """Single combined seam consumed by the HTTP layer."""

    @abstractmethod
    def process(self, audio: bytes, language: str) -> str:
        """Transcribe and normalize audio bytes into clean text."""


class StubPipeline(Pipeline):
    """Deterministic stand-in for contract tests; the real implementation lands in nlp-pipeline."""

    def process(self, audio: bytes, language: str) -> str:
        return f"stub:{language}:{len(audio)}"