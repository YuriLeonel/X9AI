"""Shared fixtures for server integration tests."""

import pytest
from fastapi.testclient import TestClient

from x9ai.app import create_app
from x9ai.pipeline import StubPipeline


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(pipeline=StubPipeline()))