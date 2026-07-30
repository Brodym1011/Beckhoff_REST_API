import pytest
from fastapi.testclient import TestClient

from source.main import app
from source.action_commands import run_action_command


client = TestClient(app)


@pytest.mark.parametrize(
    ("device_type", "device_name", "action"),
    [
        ("flex", "flex_1", "dispense"),
        ("flex", "flex_2", "drop_tip"),
        ("arm", "static_arm", "grab_sample"),
        ("arm", "tracked_arm", "drop_sample"),
        ("plc", "plc", "open_door"),
        ("plc", "plc", "close_door"),
    ],
)
def test_restful_action_returns_route_fields(
    monkeypatch,
    device_type,
    device_name,
    action,
):
    monkeypatch.setattr("source.device_routing.run_action_command", lambda a: None)
    monkeypatch.setenv(f"MOCK_{device_name.upper()}_DELAY_MS", "0")

    response = client.post(f"/api/v1/{device_type}/{device_name}/{action}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["device_type"] == device_type
    assert payload["device_name"] == device_name
    assert payload["action"] == action
    assert payload["status"] == "completed"
    assert payload["accepted"] is True


def test_mapped_command_success_returns_200(monkeypatch):
    monkeypatch.setattr(
        "source.device_routing.run_action_command",
        lambda a: (True, "dispense completed"),
    )
    response = client.post("/api/v1/flex/flex_1/dispense")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["accepted"] is True
    assert payload["message"] == "dispense completed"


def test_mapped_command_failure_returns_400(monkeypatch):
    monkeypatch.setattr(
        "source.device_routing.run_action_command",
        lambda a: (False, "script exited with code 1"),
    )
    response = client.post("/api/v1/flex/flex_1/dispense")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "ACTION_COMMAND_FAILED"
    assert "script exited with code 1" in detail["message"]


def test_unmapped_action_falls_through_to_mock(monkeypatch):
    monkeypatch.setattr("source.device_routing.run_action_command", lambda a: None)
    monkeypatch.setenv("MOCK_FLEX_1_DELAY_MS", "0")

    response = client.post("/api/v1/flex/flex_1/dispense")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_action_must_match_device_type():
    response = client.post("/api/v1/flex/flex_1/open_door")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "UNSUPPORTED_ACTION"


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/flex/flex_1/force_fail",
        "/api/v1/arm/static_arm/force_fail",
        "/api/v1/plc/plc/force_fail",
    ],
)
def test_force_fail_returns_400_for_all_device_types(url):
    response = client.post(url)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "ACTION_COMMAND_FAILED"


def test_device_name_must_match_device_type():
    response = client.post("/api/v1/arm/flex_1/grab_sample")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "UNKNOWN_DEVICE"


def test_unknown_device_type_is_rejected():
    response = client.post("/api/v1/robot/static_arm/grab_sample")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "UNKNOWN_DEVICE_TYPE"


def test_each_action_has_an_individual_fastapi_function():
    action_functions = {
        route.endpoint.__name__
        for route in app.routes
        if route.path.startswith("/api/v1/")
    }

    assert {
        "flex_dispense",
        "flex_drop_tip",
        "flex_force_fail",
        "arm_grab_sample",
        "arm_drop_sample",
        "arm_force_fail",
        "plc_open_door",
        "plc_close_door",
        "plc_force_fail",
    }.issubset(action_functions)


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/flex/not_a_flex/dispense",
        "/api/v1/arm/not_an_arm/grab_sample",
        "/api/v1/plc/not_a_plc/open_door",
    ],
)
def test_invalid_device_names_return_404(url):
    response = client.post(url)

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "UNKNOWN_DEVICE"


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/flex/flex_1/grab_sample",
        "/api/v1/flex/flex_2/close_door",
        "/api/v1/arm/static_arm/dispense",
        "/api/v1/arm/tracked_arm/open_door",
        "/api/v1/plc/plc/drop_tip",
        "/api/v1/plc/plc/drop_sample",
    ],
)
def test_invalid_actions_for_each_device_type_return_404(url):
    response = client.post(url)

    assert response.status_code == 404
    payload = response.json()["detail"]
    assert payload["error_code"] == "UNSUPPORTED_ACTION"
    assert "not supported" in payload["message"]


@pytest.mark.parametrize(
    "device_type",
    ["robot", "unknown", "Flex", "ARM", "plcs"],
)
def test_invalid_device_types_return_404(device_type):
    response = client.post(
        f"/api/v1/{device_type}/some_device/some_action"
    )

    assert response.status_code == 404
    payload = response.json()["detail"]
    assert payload["error_code"] == "UNKNOWN_DEVICE_TYPE"
    assert device_type in payload["message"]


@pytest.mark.parametrize(
    ("device_type", "wrong_name", "valid_action"),
    [
        ("flex", "static_arm", "dispense"),
        ("arm", "flex_1", "grab_sample"),
        ("plc", "flex_2", "open_door"),
    ],
)
def test_device_names_cannot_be_used_under_another_type(
    device_type,
    wrong_name,
    valid_action,
):
    response = client.post(
        f"/api/v1/{device_type}/{wrong_name}/{valid_action}"
    )

    assert response.status_code == 404
    payload = response.json()["detail"]
    assert payload["error_code"] == "UNKNOWN_DEVICE"
    assert wrong_name in payload["message"]


# ============================================================
# action_commands unit tests
# ============================================================

import sys


def test_run_action_command_runs_mapped_command(monkeypatch, tmp_path):
    config = tmp_path / "action_commands.json"
    config.write_text(f'{{"dispense": ["{sys.executable}", "-c", "print(\\"dispense ok\\")"]}}' )
    monkeypatch.setenv("ACTION_COMMANDS_FILE", str(config))

    success, message = run_action_command("dispense")
    assert success is True
    assert message == "dispense ok"


def test_run_action_command_returns_none_when_not_mapped(monkeypatch, tmp_path):
    config = tmp_path / "action_commands.json"
    config.write_text("{}")
    monkeypatch.setenv("ACTION_COMMANDS_FILE", str(config))

    assert run_action_command("dispense") is None


def test_run_action_command_returns_failure_on_nonzero_exit(monkeypatch, tmp_path):
    config = tmp_path / "action_commands.json"
    config.write_text(f'{{"dispense": ["{sys.executable}", "-c", "import sys; print(\\"hardware fault\\", file=sys.stderr); sys.exit(1)"]}}' )
    monkeypatch.setenv("ACTION_COMMANDS_FILE", str(config))

    success, message = run_action_command("dispense")
    assert success is False
    assert "hardware fault" in message


def test_run_action_command_uses_default_message_when_stdout_is_empty(monkeypatch, tmp_path):
    config = tmp_path / "action_commands.json"
    config.write_text(f'{{"dispense": ["{sys.executable}", "-c", "pass"]}}')
    monkeypatch.setenv("ACTION_COMMANDS_FILE", str(config))

    success, message = run_action_command("dispense")
    assert success is True
    assert message == "dispense completed"

