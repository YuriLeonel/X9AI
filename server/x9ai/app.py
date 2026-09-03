"""X9AI processing server: the single HTTP boundary (docs/spec.md SS6)."""

import json
import logging
import time

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from x9ai.config import Settings
from x9ai.logs import log_request
from x9ai.normalizer import RuleBasedNormalizer
from x9ai.pipeline import Pipeline, RealPipeline
from x9ai.schemas import ErrorResponse, SuccessResponse
from x9ai.transcriber import WhisperTranscriber

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


def _status_of(response) -> int:
    return response.status_code if isinstance(response, JSONResponse) else 200


async def _handle(
    audio_file: UploadFile,
    metadata: str | None,
    pipeline: Pipeline,
    settings: Settings,
):
    audio = await audio_file.read()
    if not audio:
        return _error_response(400, "audio_file must not be empty"), None
    if len(audio) > settings.max_audio_bytes:
        return _error_response(413, "audio_file exceeds maximum size"), None
    try:
        parsed = _metadata_or_default(metadata)
    except MetadataInvalid:
        return _error_response(400, "metadata must be a valid JSON object"), None

    language = parsed.get("language", "pt")
    client_timestamp = parsed.get("client_timestamp")
    try:
        start = time.perf_counter()
        text = await run_in_threadpool(pipeline.process, audio, language)
    except Exception:
        logger.exception("pipeline processing failed")
        return _error_response(500, "processing failed"), client_timestamp

    processing_time_ms = round((time.perf_counter() - start) * 1000)
    return (
        SuccessResponse(status="success", text=text, processing_time_ms=processing_time_ms),
        client_timestamp,
    )


def _real_pipeline(settings: Settings) -> Pipeline:
    return RealPipeline(WhisperTranscriber(settings), RuleBasedNormalizer())


def create_app(pipeline: Pipeline | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    pipeline = pipeline or _real_pipeline(settings)

    app = FastAPI(
        title="X9AI processing server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        log_request(method=request.method, path=request.url.path, status=400, processing_time_ms=None, client_timestamp=None)
        return _error_response(400, "invalid request")

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception while handling %s %s", request.method, request.url.path)
        log_request(method=request.method, path=request.url.path, status=500, processing_time_ms=None, client_timestamp=None)
        return _error_response(500, "processing failed")

    @app.post("/process")
    async def process(
        request: Request,
        audio_file: UploadFile = File(...),
        metadata: str | None = Form(None),
    ):
        started = time.perf_counter()
        response, client_timestamp = await _handle(audio_file, metadata, pipeline, settings)
        log_request(
            method=request.method,
            path=request.url.path,
            status=_status_of(response),
            processing_time_ms=round((time.perf_counter() - started) * 1000),
            client_timestamp=client_timestamp,
        )
        return response

    return app