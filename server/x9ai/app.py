"""X9AI processing server: the single HTTP boundary (docs/spec.md SS6)."""

import json
import time

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from x9ai.config import Settings
from x9ai.pipeline import Pipeline, StubPipeline
from x9ai.schemas import SuccessResponse

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


def create_app(pipeline: Pipeline | None = None, settings: Settings | None = None) -> FastAPI:
    pipeline = pipeline or StubPipeline()
    settings = settings or Settings()

    app = FastAPI(
        title="X9AI processing server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.post("/process")
    async def process(
        audio_file: UploadFile = File(...),
        metadata: str | None = Form(None),
    ) -> SuccessResponse:
        audio = await audio_file.read()
        parsed = _metadata_or_default(metadata)
        language = parsed.get("language", "pt")

        start = time.perf_counter()
        text = await run_in_threadpool(pipeline.process, audio, language)
        processing_time_ms = round((time.perf_counter() - start) * 1000)

        return SuccessResponse(status="success", text=text, processing_time_ms=processing_time_ms)

    return app