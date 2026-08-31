import os
from pathlib import Path

_TEST_DB = Path(__file__).resolve().parent.parent / "var" / "test-nexusops.sqlite3"
_TEST_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["NEXUSOPS_DB"] = str(_TEST_DB)

import pytest

from app import create_app
from app.config import DEMO_EMAIL, DEMO_PASSWORD


@pytest.fixture()
def client():
    application = create_app()
    application.config["TESTING"] = True
    with application.test_client() as client:
        yield client


def login(client):
    return client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        follow_redirects=True,
    )
