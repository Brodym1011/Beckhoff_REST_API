import pytest
from fastapi.testclient import TestClient

from source.main import app


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
    monkeypatch.setenv(f"MOCK_{device_name.upper()}_DELAY_MS", "0")

    response = client.post(f"/api/v1/{device_type}/{device_name}/{action}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["device_type"] == device_type
    assert payload["device_name"] == device_name
    assert payload["action"] == action
    assert payload["status"] == "completed"
    assert payload["accepted"] is True


def test_action_must_match_device_type():
    response = client.post("/api/v1/flex/flex_1/open_door")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "UNSUPPORTED_ACTION"


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
        "arm_grab_sample",
        "arm_drop_sample",
        "plc_open_door",
        "plc_close_door",
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
