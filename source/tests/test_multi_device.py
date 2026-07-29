from datetime import datetime, timezone
from uuid import UUID, uuid4
from urllib.error import URLError

from fastapi.testclient import TestClient

from source.main import app
from source.device_routing import CommandRouter, DeviceRegistry
from source.models import DeviceTarget
from fake_ipc import (
    BRANDING_PATH,
    DEFAULT_API_BASE_URL,
    DEVICE_OPTIONS,
    build_action_url,
    build_command_payload,
    build_health_url,
    check_api_health,
    format_action_response,
)


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


def test_ipc_device_and_action_options_match_api_contract():
    assert DEVICE_OPTIONS == {
        "Flex": {
            "api_value": "flex",
            "devices": {"Flex 1": "flex_1", "Flex 2": "flex_2"},
            "actions": {"Dispense": "dispense", "Drop Tip": "drop_tip"},
        },
        "Arm": {
            "api_value": "arm",
            "devices": {
                "Static Arm": "static_arm",
                "Tracked Arm": "tracked_arm",
            },
            "actions": {
                "Grab Sample": "grab_sample",
                "Drop Sample": "drop_sample",
            },
        },
        "PLC": {
            "api_value": "plc",
            "devices": {"PLC": "plc"},
            "actions": {
                "Open Door": "open_door",
                "Close Door": "close_door",
            },
        },
    }


def test_ipc_builds_restful_action_url():
    url = build_action_url(
        "http://127.0.0.1:8000/api/v1/",
        "arm",
        "static_arm",
        "grab_sample",
    )

    assert url == "http://127.0.0.1:8000/api/v1/arm/static_arm/grab_sample"


def test_ipc_echoes_device_name_and_action_in_response_log():
    summary = format_action_response(
        {
            "device_type": "flex",
            "device_name": "flex_1",
            "action": "dispense",
            "status": "completed",
            "message": "Dispense completed",
        }
    )

    assert "device_type=flex" in summary
    assert "device_name=flex_1" in summary
    assert "action=dispense" in summary
    assert "status=completed" in summary
    assert "message=Dispense completed" in summary


class FakeHealthResponse:
    def __init__(self, payload):
        import json
        self.body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def test_ipc_health_url_uses_api_base_url():
    assert build_health_url("http://127.0.0.1:8000/api/v1/") == (
        "http://127.0.0.1:8000/api/v1/system"
    )


def test_ipc_default_api_url_uses_current_host():
    assert DEFAULT_API_BASE_URL == "http://127.0.0.1:8000/api/v1"


def test_ipc_api_indicator_is_green_for_healthy_response():
    def opener(url, timeout):
        assert url.endswith("/api/v1/system")
        assert timeout == 3
        return FakeHealthResponse({"heartbeat": True})

    available, message = check_api_health("http://example/api/v1", opener)

    assert available is True
    assert message == "API Connected"


def test_ipc_api_indicator_is_red_when_connection_fails():
    def opener(_url, timeout):
        assert timeout == 3
        raise URLError("connection refused")

    available, message = check_api_health("http://example/api/v1", opener)

    assert available is False
    assert "Unable to connect to the API" in message
