"""Integration tests: per-request structured logging (SRV-11)."""

import json
import logging

from fastapi.testclient import TestClient


def _request_lines(caplog) -> list[dict]:
    lines = []
    for record in caplog.records:
        raw = record.getMessage()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("event") == "http_request":
            lines.append(parsed)
    return lines


def test_success_request_logs_structured_line_with_client_timestamp(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="x9ai"):
        client.post(
            "/process",
            files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
            data={"metadata": '{"client_timestamp": 1715000000}'},
        )
    lines = _request_lines(caplog)
    assert len(lines) == 1
    line = lines[0]
    assert line["event"] == "http_request"
    assert line["method"] == "POST"
    assert line["path"] == "/process"
    assert line["status"] == 200
    assert isinstance(line["processing_time_ms"], int)
    assert line["client_timestamp"] == 1715000000


def test_request_line_omits_client_timestamp_when_absent(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="x9ai"):
        client.post(
            "/process",
            files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        )
    line = _request_lines(caplog)[0]
    assert "client_timestamp" not in line


def test_contract_error_request_is_logged_with_status_400(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="x9ai"):
        client.post("/process", data={"metadata": "{}"})
    assert any(line["status"] == 400 for line in _request_lines(caplog))


def test_pipeline_failure_request_is_logged_with_status_500(raising_client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="x9ai"):
        raising_client.post(
            "/process",
            files={"audio_file": ("clip.wav", b"abcd", "audio/wav")},
        )
    assert any(line["status"] == 500 for line in _request_lines(caplog))