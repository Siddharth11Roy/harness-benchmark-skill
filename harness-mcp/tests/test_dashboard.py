from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from harness_mcp.dashboard import create_app
from harness_mcp.store import SessionStore

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    store = SessionStore(root=FIXTURES)
    return TestClient(create_app(store))


def test_api_sessions(client):
    r = client.get("/api/sessions")
    assert r.status_code == 200
    body = r.json()
    assert any(s["id"] == "sample_session" for s in body["sessions"])


def test_api_session_detail(client):
    r = client.get("/api/sessions/sample_session")
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["id"] == "sample_session"
    assert "score" in body and "trace" in body


def test_api_session_unknown(client):
    r = client.get("/api/sessions/nope")
    assert r.status_code == 404


def test_api_refresh(client):
    r = client.post("/api/refresh")
    assert r.status_code == 200
    assert r.json()["refreshed"] is True


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"harness" in r.content.lower()
