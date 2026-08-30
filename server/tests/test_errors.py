"""Integration tests: contract violations and pipeline failure mapping (SRV-05..08)."""

import logging

from fastapi.testclient import TestClient

from x9ai.app import create_app
from x9ai.config import Settings
from x9ai.pipeline import StubPipeline


def test_missing_audio_file_returns_400_with_error_contract(client: TestClient) -> None:
    response = client.post("/process", data={"metadata": "{}"})
    assert response.status_code == 400
    assert response.json() == {"status": "error", "message": "invalid request"}


def test_empty_audio_file_returns_400_with_error_contract(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("empty.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"
    assert response.json()["message"]


def test_invalid_metadata_json_returns_400(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        data={"metadata": "{nope"},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_metadata_that_is_not_an_object_returns_400(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        data={"metadata": "[]"},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_oversized_audio_returns_413(client: TestClient) -> None:
    tiny = TestClient(create_app(pipeline=StubPipeline(), settings=Settings(max_audio_bytes=2)))
    response = tiny.post(
        "/process",
        files={"audio_file": ("big.wav", b"12345", "audio/wav")},
    )
    assert response.status_code == 413
    assert response.json()["status"] == "error"


def test_pipeline_failure_returns_500_generic_and_logs_stack(raising_client: TestClient, caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="x9ai"):
        response = raising_client.post(
            "/process",
            files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        )
    assert response.status_code == 500
    body = response.json()
    assert body == {"status": "error", "message": "processing failed"}
    assert "boom-internal-detail" not in body["message"]
    assert "boom-internal-detail" in caplog.text