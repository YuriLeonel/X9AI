"""Observability: one structured line per handled request (SRV-11)."""

import json
import logging

logger = logging.getLogger("x9ai")


def log_request(
    *,
    method: str,
    path: str,
    status: int,
    processing_time_ms: int | None,
    client_timestamp: float | None,
) -> None:
    record = {
        "event": "http_request",
        "method": method,
        "path": path,
        "status": status,
        "processing_time_ms": processing_time_ms,
    }
    if client_timestamp is not None:
        record["client_timestamp"] = client_timestamp
    logger.info(json.dumps(record, ensure_ascii=False, separators=(",", ":")))