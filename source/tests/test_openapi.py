import json
from pathlib import Path

from source.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = PROJECT_ROOT / "openapi.json"

ACTION_PATHS = {
    "/api/v1/flex/{device_name}/dispense",
    "/api/v1/flex/{device_name}/drop_tip",
    "/api/v1/arm/{device_name}/grab_sample",
    "/api/v1/arm/{device_name}/drop_sample",
    "/api/v1/plc/{device_name}/open_door",
    "/api/v1/plc/{device_name}/close_door",
}


# Load the checked-in schema used by external API consumers.
def load_openapi_document() -> dict:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


# Confirm that the generated artifact exists and identifies OpenAPI 3.1.
def test_openapi_document_exists_and_is_version_3_1():
    document = load_openapi_document()

    assert OPENAPI_PATH.exists()
    assert document["openapi"].startswith("3.1.")


# Ensure every supported action has its own documented POST operation.
def test_openapi_documents_all_six_action_routes():
    document = load_openapi_document()

    assert ACTION_PATHS <= set(document["paths"])
    for path in ACTION_PATHS:
        assert "post" in document["paths"][path]


# Ensure action operations use the shared response containing routed fields.
def test_action_routes_reference_device_action_response():
    document = load_openapi_document()

    for path in ACTION_PATHS:
        success_schema = document["paths"][path]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        assert success_schema["$ref"].endswith("/DeviceActionResponse")

    properties = document["components"]["schemas"]["DeviceActionResponse"][
        "properties"
    ]
    assert {"device_type", "device_name", "action"} <= set(properties)


# Detect when route/model changes have not been exported to openapi.json.
def test_openapi_artifact_matches_live_fastapi_schema():
    assert load_openapi_document() == app.openapi()
