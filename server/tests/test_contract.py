"""Integration tests: POST /process happy path and response contract (docs/spec.md SS6)."""

import time

from fastapi.testclient import TestClient

from x9ai.app import create_app
from x9ai.pipeline import Pipeline


def test_exactly_one_custom_endpoint(client: TestClient) -> None:
    custom = [r for r in client.app.routes if type(r).__name__ == "APIRoute"]
    assert [(r.path, sorted(r.methods)) for r in custom] == [("/process", ["POST"])]


def test_valid_request_returns_success_contract(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"\x00\x01\x02", "audio/wav")},
        data={"metadata": '{"language": "pt", "client_timestamp": 1715000000}'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["text"] == "stub:pt:3"
    assert isinstance(body["processing_time_ms"], int)
    assert body["processing_time_ms"] >= 0


def test_metadata_absent_defaults_to_pt(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"\x00\x01\x02\x03", "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "stub:pt:4"


def test_empty_metadata_json_defaults_to_pt(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        data={"metadata": "{}"},
    )
    assert response.json()["text"] == "stub:pt:4"


def test_language_from_metadata_is_forwarded(client: TestClient) -> None:
    response = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        data={"metadata": '{"language": "en"}'},
    )
    assert response.json()["text"] == "stub:en:4"


def test_processing_time_measured_across_pipeline() -> None:
    class SlowPipeline(Pipeline):
        def process(self, audio: bytes, language: str) -> str:
            time.sleep(0.05)
            return "slow-text"

    client = TestClient(create_app(pipeline=SlowPipeline()))
    start = time.perf_counter()
    body = client.post(
        "/process",
        files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
    ).json()
    wall_ms = (time.perf_counter() - start) * 1000
    assert body["processing_time_ms"] >= 40
    assert body["processing_time_ms"] <= wall_ms + 2
    assert body["text"] == "slow-text"