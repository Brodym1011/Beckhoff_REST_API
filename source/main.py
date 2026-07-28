from fastapi import FastAPI, HTTPException, status

from backend_base import MachineBackend
from configuration import BACKEND_MODE
from mock_backend import MockBackend
from models import *


# ============================================================
# Backend configuration
# ============================================================

def create_backend() -> MachineBackend:
    if BACKEND_MODE == "mock":
        return MockBackend()

    if BACKEND_MODE == "ads":
        raise RuntimeError(
            "ADS backend is reserved for future implementation."
        )

    raise RuntimeError(
        f"Unsupported BACKEND_MODE: {BACKEND_MODE}"
    )


backend: MachineBackend = create_backend()


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="Beckhoff PLC REST API",
    version="1.2.0",
    description=(
        "Prototype 2 REST API for high-level machine commands and status.\n\n"
        "The PLC is authoritative for command acceptance, execution, "
        "physical completion, interlocks, timing, and faults.\n\n"
        "An HTTP 202 response means that a command request was received by "
        "the API. It does not mean that the physical operation has completed."
    ),
)

API_PREFIX = "/api/v1"


DOOR_COMMANDS = {
    DeviceCommand.Open,
    DeviceCommand.Close,
    DeviceCommand.ResetFault,
    DeviceCommand.ClearCommand,
}

DISPENSER_COMMANDS = {
    DeviceCommand.Trigger,
    DeviceCommand.ResetFault,
    DeviceCommand.ClearCommand,
}


# ============================================================
# Shared helpers
# ============================================================

def validate(command, allowed_commands):
    if command not in allowed_commands:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid command {command.name}",
        )


def response(command):
    return {
        "accepted": command.accepted,
        "status": serialize_api(command.status),
        "message": command.status_message,
        "request_id": command.request_id,
    }


# ============================================================
# System and machine status
# ============================================================

@app.get(
    f"{API_PREFIX}/system",
    tags=["System"],
    summary="Get API and communication status",
    description=(
        "Returns REST API version information, backend status, and the API "
        "heartbeat. Machine execution and fault state remain authoritative "
        "in the PLC."
    ),
)
def system():
    return serialize_api(
        backend.get_system_status()
    )


@app.get(
    f"{API_PREFIX}/machine/snapshot",
    tags=["Machine"],
    summary="Get complete machine snapshot",
    description=(
        "Returns the current machine, engineering, input, output, command, "
        "and supported device states in one response."
    ),
)
def snapshot():
    return serialize_api(
        backend.get_snapshot()
    )


@app.get(
    f"{API_PREFIX}/machine/status",
    tags=["Machine"],
    summary="Get machine-level status",
    description=(
        "Returns high-level machine readiness, busy state, fault state, "
        "simulation state, and most recent fault information."
    ),
)
def machine_status():
    return serialize_api(
        backend.get_machine_status()
    )


@app.get(
    f"{API_PREFIX}/machine/outputs",
    tags=["Machine"],
    summary="Get semantic machine outputs",
    description=(
        "Returns machine-function output names such as door open and close "
        "outputs. Physical terminal, channel, and PLC symbol mappings are "
        "not part of the public API contract."
    ),
)
def machine_outputs():
    return serialize_api(
        backend.get_machine_outputs()
    )


# ============================================================
# Device status
# ============================================================

@app.get(
    f"{API_PREFIX}/devices",
    tags=["Devices"],
    summary="List supported device states",
    description=(
        "Returns status for the currently supported Door 1, Door 2, and "
        "dispenser devices."
    ),
)
def devices():
    return serialize_api(
        {
            "devices": backend.get_all_devices()
        }
    )


@app.get(
    f"{API_PREFIX}/devices/door1",
    tags=["Devices"],
    summary="Get Door 1 status",
    description=(
        "Returns the high-level Door 1 state, position, sensors, command "
        "tracking information, and faults."
    ),
)
def door1():
    return serialize_api(
        backend.get_door1_status()
    )


@app.get(
    f"{API_PREFIX}/devices/door2",
    tags=["Devices"],
    summary="Get Door 2 status",
    description=(
        "Returns the high-level Door 2 state, position, sensors, command "
        "tracking information, and faults."
    ),
)
def door2():
    return serialize_api(
        backend.get_door2_status()
    )


@app.get(
    f"{API_PREFIX}/devices/dispenser",
    tags=["Devices"],
    summary="Get dispenser status",
    description=(
        "Returns the currently supported high-level dispenser state. "
        "The final dispenser command and EL6001 serial contract remain "
        "pending PLC checkpoint verification."
    ),
)
def dispenser():
    return serialize_api(
        backend.get_dispenser_status()
    )


@app.get(
    f"{API_PREFIX}/devices/igus_axis",
    tags=["Devices"],
    summary="Get reserved igus axis contract status",
    description=(
        "Reserves the public igus_axis device name for Prototype 2. "
        "The final motion command list, position fields, units, speeds, "
        "profiles, and drive mapping are intentionally not defined yet."
    ),
)
def igus_axis():
    return {
        "device": "igus_axis",
        "status": "reserved",
        "contract_finalized": False,
    }


# ============================================================
# Command status
# ============================================================

@app.get(
    f"{API_PREFIX}/commands/door1",
    tags=["Command Status"],
    summary="Get Door 1 command status",
    description=(
        "Returns the most recent Door 1 command lifecycle and result."
    ),
)
def cd1():
    return serialize_api(
        backend.get_door1_command()
    )


@app.get(
    f"{API_PREFIX}/commands/door2",
    tags=["Command Status"],
    summary="Get Door 2 command status",
    description=(
        "Returns the most recent Door 2 command lifecycle and result."
    ),
)
def cd2():
    return serialize_api(
        backend.get_door2_command()
    )


@app.get(
    f"{API_PREFIX}/commands/dispenser",
    tags=["Command Status"],
    summary="Get dispenser command status",
    description=(
        "Returns the most recent dispenser command lifecycle and result."
    ),
)
def cdisp():
    return serialize_api(
        backend.get_dispenser_command()
    )


@app.get(
    f"{API_PREFIX}/commands/machine",
    tags=["Command Status"],
    summary="Get machine command status",
    description=(
        "Returns the most recent supported machine-level command lifecycle "
        "and result."
    ),
)
def cmach():
    return serialize_api(
        backend.get_machine_command()
    )


@app.get(
    f"{API_PREFIX}/commands/engineering",
    tags=["Command Status"],
    summary="Get engineering command status",
    description=(
        "Returns the most recent engineering-only command lifecycle and "
        "result. Engineering behavior is separate from production behavior."
    ),
)
def ceng():
    return serialize_api(
        backend.get_engineering_command()
    )


# ============================================================
# Command submission
# ============================================================

@app.post(
    f"{API_PREFIX}/commands/door1",
    tags=["Commands"],
    summary="Submit a Door 1 command",
    description=(
        "Submits a high-level Door 1 Open, Close, ResetFault, or "
        "ClearCommand request. The PLC controls outputs, sensors, timing, "
        "interlocks, completion, and faults."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": (
                "Request received by the API. Physical door operation may "
                "still be pending, executing, rejected, or faulted."
            )
        },
        400: {
            "description": "Unsupported Door 1 command."
        },
        422: {
            "description": "Invalid request body or enum value."
        },
    },
)
def pd1(request: CommandRequest):
    validate(
        request.command,
        DOOR_COMMANDS,
    )

    return response(
        backend.submit_door1_command(request)
    )


@app.post(
    f"{API_PREFIX}/commands/door2",
    tags=["Commands"],
    summary="Submit a Door 2 command",
    description=(
        "Submits a high-level Door 2 Open, Close, ResetFault, or "
        "ClearCommand request. The PLC controls outputs, sensors, timing, "
        "interlocks, completion, and faults."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": (
                "Request received by the API. Physical door operation may "
                "still be pending, executing, rejected, or faulted."
            )
        },
        400: {
            "description": "Unsupported Door 2 command."
        },
        422: {
            "description": "Invalid request body or enum value."
        },
    },
)
def pd2(request: CommandRequest):
    validate(
        request.command,
        DOOR_COMMANDS,
    )

    return response(
        backend.submit_door2_command(request)
    )


@app.post(
    f"{API_PREFIX}/commands/dispenser",
    tags=["Commands"],
    summary="Submit a dispenser command",
    description=(
        "Submits a currently supported high-level dispenser request. "
        "Raw RS-232 strings and direct EL6001 control are not exposed. "
        "The final dispenser contract remains pending PLC verification."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": (
                "Request received by the API. Dispenser completion must be "
                "confirmed through command or device status."
            )
        },
        400: {
            "description": "Unsupported dispenser command."
        },
        422: {
            "description": "Invalid request body or enum value."
        },
    },
)
def pdisp(request: CommandRequest):
    validate(
        request.command,
        DISPENSER_COMMANDS,
    )

    return response(
        backend.submit_dispenser_command(request)
    )


@app.post(
    f"{API_PREFIX}/commands/machine",
    tags=["Commands"],
    summary="Submit a machine-level command",
    description=(
        "Submits a supported high-level machine command. Normal motion Stop "
        "behavior is not exposed in Prototype 2."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": (
                "Machine command request received by the API."
            )
        },
        422: {
            "description": "Invalid request body or enum value."
        },
    },
)
def pmach(request: MachineCommandRequest):
    return response(
        backend.submit_machine_command(request)
    )


@app.post(
    f"{API_PREFIX}/commands/engineering",
    tags=["Engineering"],
    summary="Submit an engineering-only command",
    description=(
        "Submits simulation and diagnostic commands intended for engineering "
        "use only. These operations are not part of normal production "
        "behavior."
    ),
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": (
                "Engineering command request received by the API."
            )
        },
        422: {
            "description": "Invalid request body or enum value."
        },
    },
)
def peng(request: EngineeringCommandRequest):
    return response(
        backend.submit_engineering_command(request)
    )


# ============================================================
# Deprecated compatibility routes
# ============================================================

# Production routes use the /api/v1 prefix.
# These routes remain temporarily available for compatibility.

app.add_api_route(
    "/api/machine/snapshot",
    snapshot,
    methods=["GET"],
    deprecated=True,
    include_in_schema=True,
    tags=["Legacy"],
    summary="Legacy machine snapshot route",
    description=(
        "Deprecated compatibility route. "
        "Use GET /api/v1/machine/snapshot."
    ),
)

app.add_api_route(
    "/api/devices/door1/commands",
    pd1,
    methods=["POST"],
    deprecated=True,
    include_in_schema=True,
    tags=["Legacy"],
    summary="Legacy Door 1 command route",
    description=(
        "Deprecated compatibility route. "
        "Use POST /api/v1/commands/door1."
    ),
)

app.add_api_route(
    "/api/devices/door2/commands",
    pd2,
    methods=["POST"],
    deprecated=True,
    include_in_schema=True,
    tags=["Legacy"],
    summary="Legacy Door 2 command route",
    description=(
        "Deprecated compatibility route. "
        "Use POST /api/v1/commands/door2."
    ),
)

app.add_api_route(
    "/api/devices/dispenser/commands",
    pdisp,
    methods=["POST"],
    deprecated=True,
    include_in_schema=True,
    tags=["Legacy"],
    summary="Legacy dispenser command route",
    description=(
        "Deprecated compatibility route. "
        "Use POST /api/v1/commands/dispenser."
    ),
)

app.add_api_route(
    "/api/machine/commands",
    pmach,
    methods=["POST"],
    deprecated=True,
    include_in_schema=True,
    tags=["Legacy"],
    summary="Legacy machine command route",
    description=(
        "Deprecated compatibility route. "
        "Use POST /api/v1/commands/machine."
    ),
)

app.add_api_route(
    "/api/engineering/commands",
    peng,
    methods=["POST"],
    deprecated=True,
    include_in_schema=True,
    tags=["Legacy"],
    summary="Legacy engineering command route",
    description=(
        "Deprecated compatibility route. "
        "Use POST /api/v1/commands/engineering."
    ),
)