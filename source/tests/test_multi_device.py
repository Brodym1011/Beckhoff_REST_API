from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from source.main import app
from source.device_routing import CommandRouter, DeviceRegistry
from source.models import DeviceTarget
from fake_ipc import BRANDING_PATH, build_command_payload


client = TestClient(app)


def command(target: str) -> dict:
    return {
        "request_id": str(uuid4()),
        "target_device": target,
        "command": "communication_test",
        "parameters": {},
        "source": "fake_ipc",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timeout_ms": 1000,
    }


def test_all_five_targets_route_successfully():
    for target in ("flex_1", "flex_2", "plc", "static_arm", "tracked_arm"):
        response = client.post("/api/v1/commands", json=command(target))
        assert response.status_code == 200
        assert response.json()["target_device"] == target
        assert response.json()["status"] == "completed"
        assert response.json()["accepted"] is True
        assert response.json()["message"] == "Communication successful"
        assert response.json()["error_code"] is None


def test_unknown_target_is_rejected():
    response = client.post("/api/v1/commands", json=command("unknown"))
    assert response.status_code == 422


def test_unsupported_command_is_rejected():
    payload = command("plc")
    payload["command"] = "do_something"
    response = client.post("/api/v1/commands", json=payload)
    assert response.status_code == 422


def test_ipc_builds_valid_unique_command_envelopes():
    first = build_command_payload("flex_1")
    second = build_command_payload("flex_1")

    UUID(first["request_id"])
    datetime.fromisoformat(first["timestamp"])
    assert first["request_id"] != second["request_id"]
    assert first["target_device"] == "flex_1"
    assert first["command"] == "communication_test"
    assert first["parameters"] == {}
    assert first["source"] == "fake_ipc"
    assert first["timeout_ms"] == 10000


def test_ipc_branding_asset_exists_and_is_transparent_png():
    assert BRANDING_PATH.exists()
    assert BRANDING_PATH.name == "ancera_branding_transparent.png"
    assert BRANDING_PATH.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_unavailable_outcome_is_normalized(monkeypatch):
    monkeypatch.setenv("MOCK_FLEX_1_OUTCOME", "unavailable")
    monkeypatch.setenv("MOCK_FLEX_1_DELAY_MS", "0")

    response = client.post("/api/v1/commands", json=command("flex_1"))

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["message"] == "Device unavailable"
    assert response.json()["error_code"] == "DEVICE_UNAVAILABLE"


def test_failure_outcome_is_normalized(monkeypatch):
    monkeypatch.setenv("MOCK_PLC_OUTCOME", "failure")
    monkeypatch.setenv("MOCK_PLC_DELAY_MS", "0")

    response = client.post("/api/v1/commands", json=command("plc"))

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["message"] == "Communication failed"
    assert response.json()["error_code"] == "INTERNAL_ROUTING_ERROR"


def test_timeout_outcome_is_normalized(monkeypatch):
    monkeypatch.setenv("MOCK_TRACKED_ARM_OUTCOME", "timeout")
    payload = command("tracked_arm")
    payload["timeout_ms"] = 100

    response = client.post("/api/v1/commands", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "timed_out"
    assert response.json()["message"] == "Communication timed out"
    assert response.json()["error_code"] == "DEVICE_TIMEOUT"


def test_router_reports_unregistered_adapter():
    empty_router = CommandRouter(DeviceRegistry())
    payload = command("static_arm")
    from source.models import MultiDeviceCommandRequest

    request = MultiDeviceCommandRequest.model_validate(payload)
    try:
        empty_router.route(request)
    except LookupError as exc:
        assert str(exc) == "ADAPTER_NOT_REGISTERED"
    else:
        raise AssertionError("Expected an unregistered adapter error")


def test_device_target_contains_exactly_five_approved_ids():
    assert {target.value for target in DeviceTarget} == {
        "flex_1",
        "flex_2",
        "plc",
        "static_arm",
        "tracked_arm",
    }
