"""Unit tests for the HTTP response schemas (docs/spec.md SS6.2, SRV-02)."""

import pytest
from pydantic import ValidationError

from x9ai.schemas import ErrorResponse, SuccessResponse


def test_success_response_serializes_to_spec_shape() -> None:
    payload = SuccessResponse(status="success", text="Olá, mundo.", processing_time_ms=1450).model_dump()
    assert payload == {
        "status": "success",
        "text": "Olá, mundo.",
        "processing_time_ms": 1450,
    }


def test_success_response_rejects_negative_processing_time() -> None:
    with pytest.raises(ValidationError):
        SuccessResponse(status="success", text="x", processing_time_ms=-1)


def test_success_response_rejects_wrong_status() -> None:
    with pytest.raises(ValidationError):
        SuccessResponse(status="ok", text="x", processing_time_ms=1)  # type: ignore[arg-type]


def test_error_response_serializes_to_spec_shape() -> None:
    payload = ErrorResponse(status="error", message="Processing failed").model_dump()
    assert payload == {"status": "error", "message": "Processing failed"}


def test_error_response_rejects_wrong_status() -> None:
    with pytest.raises(ValidationError):
        ErrorResponse(status="error-ish", message="x")  # type: ignore[arg-type]