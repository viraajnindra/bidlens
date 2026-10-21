import os
import tempfile

# Must be set before importing application modules; tests never touch the user's database.
_test_dir = tempfile.TemporaryDirectory(prefix="bidlens-test-")
os.environ["DATA_DIR"] = _test_dir.name
os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir.name}/test.db"
os.environ.pop("BIDLENS_API_TOKEN", None)

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.models import Base, engine


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as test_client:
        yield test_client
