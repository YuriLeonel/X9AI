"""Integration tests: create_app real default pipeline (NLP-03, NLP-07)."""

from unittest import mock
from unittest.mock import patch

from fastapi.testclient import TestClient

from x9ai.app import create_app
from x9ai.normalizer import RuleBasedNormalizer
from x9ai.pipeline import RealPipeline
from x9ai.transcriber import Transcriber


class _FakeTranscriber(Transcriber):
    def transcribe(self, audio: bytes, language: str) -> str:
        return "o tipo então é bom"


def test_create_app_default_boots_without_faster_whisper() -> None:
    app = create_app()
    assert any(type(r).__name__ == "APIRoute" and r.path == "/process" for r in app.routes)


def test_create_app_default_is_real_pipeline() -> None:
    with patch("x9ai.app.RealPipeline", wraps=RealPipeline) as mock:
        create_app()
        mock.assert_called_once()


def test_create_app_default_normalizes_transcription() -> None:
    with mock.patch("x9ai.app.WhisperTranscriber", return_value=_FakeTranscriber()):
        client = TestClient(create_app())
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"\x00\x01\x02", "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "O é bom."

def test_process_routes_through_real_pipeline_end_to_end() -> None:
    pipeline = RealPipeline(_FakeTranscriber(), RuleBasedNormalizer())
    client = TestClient(create_app(pipeline=pipeline))
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"\x00\x01\x02", "audio/wav")},
        data={"metadata": '{"language": "pt"}'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["text"] == "O é bom."
    assert isinstance(body["processing_time_ms"], int)
    assert body["processing_time_ms"] >= 0
