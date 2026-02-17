"""Pytest fixtures for integration tests."""

import pytest

try:
    from app import app
    from fastapi.testclient import TestClient
    HAS_APP = True
except ImportError:
    HAS_APP = False


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    if not HAS_APP:
        pytest.skip("Full app not importable (missing weasyprint or other dependency)")
    return TestClient(app)
