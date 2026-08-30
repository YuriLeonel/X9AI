"""Unit tests for the pipeline seam (SRV-09) and its deterministic stub."""

import pytest

from x9ai.pipeline import Pipeline, StubPipeline


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