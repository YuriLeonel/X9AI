"""HTTP response contract from docs/spec.md SS6.2."""

from typing import Literal

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    status: Literal["success"]
    text: str
    processing_time_ms: int = Field(ge=0)


class ErrorResponse(BaseModel):
    status: Literal["error"]
    message: str