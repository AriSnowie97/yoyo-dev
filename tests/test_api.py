import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_health_and_index(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200


def test_task_flow_and_status_aliases(client):
    assert client.post("/api/task/start", json={"task_name": "Editing", "emoji": "✏️"}).json() == {"ok": True}
    s = client.get("/api/status").json()
    assert s["status"] == "WORKING" and s["task_name"] == "Editing" and s["task_source"] == "EXTERNAL"
    assert client.post("/api/task/update", json={"task_name": "Testing", "progress": 0.5}).status_code == 200
    s = client.get("/api/status").json()
    assert s["current_task"] == "Testing" and s["progress"] == 0.5
    assert client.post("/api/task/stop").status_code == 200
    assert client.get("/api/status").json()["status"] == "DONE"
    assert client.get("/api/stats").json()["tasks_completed"] == 1


def test_validation_rejects_bad_input(client):
    assert client.post("/api/task/update", json={"progress": 3}).status_code == 422
    assert client.post("/api/task/start", json={"task_name": ""}).status_code == 422
    assert client.post("/api/notify", json={"title": "x", "bonus_pts": 9999}).status_code == 422
    assert client.post("/api/tracker", json={"state": "BOGUS"}).status_code == 422


def test_business_rules_map_to_http_codes(client, clock):
    assert client.post("/api/task/stop").status_code == 409          # no active task
    assert client.post("/api/trick", json={"trick_name": "Nope"}).status_code == 422
    assert client.post("/api/trick", json={"trick_name": "Sleeper"}).json()["score"] == 5
    assert client.post("/api/trick", json={"trick_name": "Sleeper"}).status_code == 429
    clock.advance(1)
    assert client.post("/api/trick", json={"trick_name": "Loop the Loop"}).json()["score"] == 35


def test_websocket_snapshot_and_live_events(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "agent_state"
        client.post("/api/task/start", json={"task_name": "Live"})
        assert ws.receive_json()["current_task"] == "Live"
        client.post("/api/notify", json={"title": "Hi", "message": "m", "bonus_pts": 10})
        msg = ws.receive_json()
        assert msg["type"] == "notification" and msg["bonus_pts"] == 10


def test_tracker_reports_player_presence(client):
    client.post("/api/tracker", json={"state": "PLAYING", "detail": "YoYo Dev"})
    assert client.get("/api/status").json()["player_present"] is True
    client.post("/api/tracker", json={"state": "IDE", "detail": "main.py"})
    assert client.get("/api/status").json()["player_present"] is False


def test_read_cache_is_invalidated_by_events(client, container):
    client.get("/api/status")
    client.get("/api/status")
    assert container.queries._state_cache.hits >= 1
    client.post("/api/task/start", json={"task_name": "Fresh"})
    assert client.get("/api/status").json()["current_task"] == "Fresh"
