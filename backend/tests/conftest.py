import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend dir is on sys.path so `import app` works
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402
from backend.core.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_data_file(tmp_path, monkeypatch):
    test_data_file = tmp_path / "prospects_test.json"
    monkeypatch.setattr(settings, "DATA_FILE", str(test_data_file))
    yield


@pytest.fixture()
def client():
    return TestClient(app)
