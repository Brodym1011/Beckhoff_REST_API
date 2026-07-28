import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app


client = TestClient(app)


def test_system_endpoint_returns_status_payload():
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "1.1"
    assert payload["project_version"] == "mock"
    assert payload["heartbeat"] is True


def test_machine_status_endpoint_returns_machine_state():
    response = client.get("/api/v1/machine/status")

    assert response.status_code == 200
    payload = response.json()
    assert "ready" in payload
    assert "busy" in payload
    assert "fault" in payload


def test_door1_command_accepts_valid_request():
    response = client.post(
        "/api/v1/commands/door1",
        json={
            "command": 1,
            "request_id": 101,
            "source": 2,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["request_id"] == 101


def test_door1_command_rejects_invalid_command():
    response = client.post(
        "/api/v1/commands/door1",
        json={
            "command": 3,
            "request_id": 102,
            "source": 2,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert "detail" in payload
