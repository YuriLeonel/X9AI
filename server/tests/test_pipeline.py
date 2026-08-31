"""Unit tests for the pipeline seam (SRV-09) and its deterministic stub."""

import pytest

from x9ai.normalizer import RuleBasedNormalizer
from x9ai.pipeline import Pipeline, RealPipeline, StubPipeline
from x9ai.transcriber import Transcriber


class _FakeTranscriber(Transcriber):
    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio: bytes, language: str) -> str:
        return self.text


class _RaisingTranscriber(Transcriber):
    def transcribe(self, audio: bytes, language: str) -> str:
        raise RuntimeError("boom")


def test_pipeline_is_abstract() -> None:
    with pytest.raises(TypeError):
        Pipeline()  # type: ignore[abstract]


def test_stub_derives_language_and_bytes_length() -> None:
    result = StubPipeline().process(b"\x00\x01\x02", "pt")
    assert result == "stub:pt:3"


def test_stub_is_deterministic() -> None:
    pipeline = StubPipeline()
    assert pipeline.process(b"abc", "en") == pipeline.process(b"abc", "en")


def test_stub_edge_sizes() -> None:
    pipeline = StubPipeline()
    assert pipeline.process(b"", "pt") == "stub:pt:0"
    assert pipeline.process(b"\x00" * 10, "en") == "stub:en:10"


def test_real_pipeline_implements_pipeline_interface() -> None:
    pipeline = RealPipeline(_FakeTranscriber("x"), RuleBasedNormalizer())
    assert isinstance(pipeline, Pipeline)


def test_real_pipeline_normalizes_transcriber_output() -> None:
    pipeline = RealPipeline(_FakeTranscriber("o tipo então é bom"), RuleBasedNormalizer())
    assert pipeline.process(b"\x00", "pt") == "O é bom."


def test_real_pipeline_passes_language_to_transcriber() -> None:
    received = {}

    class _LanguageAware(Transcriber):
        def transcribe(self, audio: bytes, language: str) -> str:
            received["language"] = language
            return "ola"

    pipeline = RealPipeline(_LanguageAware(), RuleBasedNormalizer())
    pipeline.process(b"\x00", "en")
    assert received == {"language": "en"}


def test_real_pipeline_propagates_transcriber_exception() -> None:
    pipeline = RealPipeline(_RaisingTranscriber(), RuleBasedNormalizer())
    with pytest.raises(RuntimeError, match="boom"):
        pipeline.process(b"\x00", "pt")