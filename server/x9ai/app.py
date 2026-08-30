"""X9AI processing server: the single HTTP boundary (docs/spec.md SS6)."""

import json
import logging
import time

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from x9ai.config import Settings
from x9ai.pipeline import Pipeline, StubPipeline
from x9ai.schemas import ErrorResponse, SuccessResponse

logger = logging.getLogger("x9ai")

METADATA_DEFAULT = {"language": "pt"}


class MetadataInvalid(ValueError):
    """Raised when the metadata field is not a valid JSON object."""


def _metadata_or_default(metadata: str | None) -> dict:
    if not metadata:
        return METADATA_DEFAULT
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise MetadataInvalid("metadata must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise MetadataInvalid("metadata must be a JSON object")
    return parsed


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(status="error", message=message).model_dump(),
    )


def create_app(pipeline: Pipeline | None = None, settings: Settings | None = None) -> FastAPI:
    pipeline = pipeline or StubPipeline()
    settings = settings or Settings()

    app = FastAPI(
        title="X9AI processing server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(400, "invalid request")

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception while handling %s %s", request.method, request.url.path)
        return _error_response(500, "processing failed")

    @app.post("/process")
    async def process(
        audio_file: UploadFile = File(...),
        metadata: str | None = Form(None),
    ):
        audio = await audio_file.read()
        if not audio:
            return _error_response(400, "audio_file must not be empty")
        if len(audio) > settings.max_audio_bytes:
            return _error_response(413, "audio_file exceeds maximum size")
        try:
            parsed = _metadata_or_default(metadata)
        except MetadataInvalid:
            return _error_response(400, "metadata must be a valid JSON object")
        language = parsed.get("language", "pt")

        start = time.perf_counter()
        text = await run_in_threadpool(pipeline.process, audio, language)
        processing_time_ms = round((time.perf_counter() - start) * 1000)

        return SuccessResponse(status="success", text=text, processing_time_ms=processing_time_ms)

    return app