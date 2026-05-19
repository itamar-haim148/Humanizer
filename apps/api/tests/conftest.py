"""Pytest fixtures shared across the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the api package importable when running pytest from apps/api.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(create_app())
