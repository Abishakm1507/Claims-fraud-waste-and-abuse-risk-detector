import pytest
from fastapi.testclient import TestClient

from backend.app.data.repository import repository
from backend.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def repo():
    return repository
