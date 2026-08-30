"""Unit tests for the faster-whisper transcription seam (NLP-05..09)."""

import sys

import pytest

from x9ai.config import Settings
from x9ai.transcriber import Transcriber, WhisperTranscriber


class _Segment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def transcribe(self, stream, language=None):
        return [_Segment(f"ola {len(stream.getvalue())}"), _Segment("tudo bem")], {}


def test_transcriber_is_abstract() -> None:
    with pytest.raises(TypeError):
        Transcriber()  # type: ignore[abstract]


def test_constructs_without_faster_whisper() -> None:
    transcriber = WhisperTranscriber()
    assert transcriber.model_name == "medium"
    assert "faster_whisper" not in sys.modules


def test_model_name_reports_configured_model() -> None:
    settings = Settings(whisper_model="large-v3")
    assert WhisperTranscriber(settings=settings).model_name == "large-v3"


def test_transcribe_joins_segments_via_model_factory() -> None:
    captured = {}

    def factory(settings: Settings) -> object:
        captured["model"] = settings.whisper_model
        captured["device"] = settings.whisper_device
        captured["compute_type"] = settings.whisper_compute_type
        return _FakeModel()

    transcriber = WhisperTranscriber(model_factory=factory)
    result = transcriber.transcribe(b"\x00audio", "pt")
    assert result == "ola 6 tudo bem"
    assert captured == {"model": "medium", "device": "auto", "compute_type": "default"}


def test_model_factory_invoked_only_on_transcribe() -> None:
    calls = []

    def factory(settings: Settings) -> object:
        calls.append(1)
        return _FakeModel()

    transcriber = WhisperTranscriber(model_factory=factory)
    assert calls == []
    transcriber.transcribe(b"x", "pt")
    assert calls == [1]


def test_language_passed_to_model() -> None:
    seen = {}

    def factory(settings: Settings) -> object:
        model = _FakeModel()
        original = model.transcribe
        model.transcribe = lambda stream, language=None: (seen.update(language=language), original(stream, language))[1]
        return model

    WhisperTranscriber(model_factory=factory).transcribe(b"\x00", "en")
    assert seen == {"language": "en"}


def test_default_factory_raises_import_error_without_faster_whisper() -> None:
    transcriber = WhisperTranscriber()
    with pytest.raises(ImportError):
        transcriber.transcribe(b"\x00", "pt")
