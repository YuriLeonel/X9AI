"""Shared fixtures for server integration tests."""

import pytest
from fastapi.testclient import TestClient

from x9ai.app import create_app
from x9ai.pipeline import Pipeline, StubPipeline


class BoomPipeline(Pipeline):
    """Pipeline that always fails; proves SRV-08 generic error mapping."""

    def process(self, audio: bytes, language: str) -> str:
        raise RuntimeError("boom-internal-detail")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(pipeline=StubPipeline()))


@pytest.fixture
def raising_client() -> TestClient:
    return TestClient(create_app(pipeline=BoomPipeline()), raise_server_exceptions=False)