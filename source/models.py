from enum import IntEnum
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, Field


# ============================================================
# Enumerations
# ============================================================

class DeviceState(IntEnum):
    Idle = 0
    Commanded = 1
    InProgress = 2
    Complete = 3
    Fault = 4


class DoorPosition(IntEnum):
    Unknown = 0
    Closed = 1
    Open = 2
    Fault = 3


class FaultCode(IntEnum):
    NoneFault = 0
    TimeoutNoFeedback = 1
    UnexpectedTrigger = 2
    OutputDriverFault = 3
    AnalogOutOfRange = 4
    Busy = 5


class DeviceCommand(IntEnum):
    NoneCommand = 0
    Open = 1
    Close = 2
    Trigger = 3
    ResetFault = 4
    Home = 5
    ClearCommand = 6


class CommandSource(IntEnum):
    NoneSource = 0
    PLC = 1
    IPC = 2
    Manual = 3


class CommandStatus(IntEnum):
    NoneStatus = 0
    Received = 1
    Pending = 2
    Accepted = 3
    Executing = 4
    Complete = 5
    Rejected = 6
    Faulted = 7
    Busy = 8


class CommandResult(IntEnum):
    NoneResult = 0
    Accepted = 1
    Busy = 2
    Complete = 3
    Rejected = 4
    Faulted = 5


class DeviceID(IntEnum):
    NoneDevice = 0
    Dispenser = 1
    Door1 = 2
    Door2 = 3

    # Reserved Prototype 2 public device name.
    IgusAxis = 4

    # Backward-compatible alias for older internal code.
    Robot = 4


class CommandRejectCode(IntEnum):
    NoneReject = 0
    DeviceFaulted = 1
    DeviceBusy = 2
    AlreadyOpen = 3
    AlreadyClosed = 4
    InvalidDoorCommand = 5
    InvalidDispenserCommand = 6
    InvalidDevice = 7
    InvalidRequestID = 8
    DuplicateRequestID = 9
    InvalidCommandSource = 10
    InvalidSimulatedSensorState = 11


class MachineCommand(IntEnum):
    NoneCommand = 0
    ClearLastFault = 1


class EngineeringCommand(IntEnum):
    NoneCommand = 0
    EnableSimulationMode = 1
    DisableSimulationMode = 2
    EnableOutputSuppression = 3
    DisableOutputSuppression = 4
    ClearSimulatedInputs = 5

    # Neutral public dispenser terminology.
    SetSimDispenserRunningFeedback = 6

    SetSimDoor1OpenSensor = 7
    SetSimDoor1ClosedSensor = 8
    SetSimDoor2OpenSensor = 9
    SetSimDoor2ClosedSensor = 10
    SetSimDoor1Position = 11
    SetSimDoor2Position = 12

    # Backward-compatible alias for existing backend code.
    SetSimPumpRunningFeedback = 6


# ============================================================
# Request and response models
# ============================================================

class CommandRequest(BaseModel):
    command: DeviceCommand
    request_id: int
    source: CommandSource = CommandSource.IPC
    parameter1: Optional[int | float | str] = None
    parameter2: Optional[int | float | str] = None


class MachineCommandRequest(BaseModel):
    command: MachineCommand
    request_id: int
    source: CommandSource = CommandSource.IPC


class EngineeringCommandRequest(BaseModel):
    command: EngineeringCommand
    request_id: int
    source: CommandSource = CommandSource.IPC
    parameter1: Optional[int | float | str] = None
    parameter2: Optional[int | float | str] = None


class CommandResponse(BaseModel):
    accepted: bool
    status: Any
    message: str
    request_id: int


# ============================================================
# Command and device status models
# ============================================================

class CommandModel(BaseModel):
    execute: bool = False
    command: Any = 0
    source: CommandSource = CommandSource.NoneSource
    request_id: int = 0
    status: CommandStatus = CommandStatus.NoneStatus
    status_message: str = ""
    time_received: Optional[str] = None
    parameter1: Optional[Any] = None
    parameter2: Optional[Any] = None
    accepted: bool = False
    completed: bool = False
    result: CommandResult = CommandResult.NoneResult
    reject_code: CommandRejectCode = CommandRejectCode.NoneReject
    duplicate_request_detected: bool = False
    last_completed_request_id: int = 0


class DeviceStatus(BaseModel):
    device_id: DeviceID
    state: DeviceState = DeviceState.Idle
    cycle_count: int = 0
    fault_count: int = 0
    active_request_id: Optional[int] = 0
    last_completed_request_id: Optional[int] = 0
    last_command_time: Optional[str] = None
    last_complete_time: Optional[str] = None
    operation_time_ms: int = 0
    fault_code: FaultCode = FaultCode.NoneFault
    fault_active: bool = False
    busy: bool = False
    position: Optional[DoorPosition] = None
    open_sensor_active: Optional[bool] = None
    closed_sensor_active: Optional[bool] = None


class IgusAxisStatus(BaseModel):
    """
    Reserved model location for the Prototype 2 igus_axis device.

    Do not add motion commands, position units, speed fields, drive I/O,
    or final status fields until the PLC checkpoints establish the contract.
    """


# ============================================================
# Machine-level status
# ============================================================

class MachineStatus(BaseModel):
    ready: bool = True
    busy: bool = False
    fault: bool = False
    simulation_mode: bool = False
    suppress_physical_outputs_in_simulation: bool = False
    physical_outputs_suppressed: bool = False
    last_fault: FaultCode = FaultCode.NoneFault
    last_fault_device: DeviceID = DeviceID.NoneDevice


class EngineeringStatus(BaseModel):
    simulation_mode: bool = False
    suppress_physical_outputs_in_simulation: bool = False
    physical_outputs_suppressed: bool = False

    sim_dispenser_running_feedback: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "sim_dispenser_running_feedback",
            "sim_pump_running_feedback",
        ),
    )

    sim_door1_open_sensor: bool = False
    sim_door1_closed_sensor: bool = True
    sim_door2_open_sensor: bool = False
    sim_door2_closed_sensor: bool = True

    # Compatibility for existing backend code.
    @property
    def sim_pump_running_feedback(self) -> bool:
        return self.sim_dispenser_running_feedback

    @sim_pump_running_feedback.setter
    def sim_pump_running_feedback(self, value: bool) -> None:
        self.sim_dispenser_running_feedback = value


# ============================================================
# Inputs
# ============================================================

class DigitalInputStatus(BaseModel):
    state: bool = False


class MachineInputs(BaseModel):
    dispenser_running_feedback: DigitalInputStatus = Field(
        default_factory=DigitalInputStatus,
        validation_alias=AliasChoices(
            "dispenser_running_feedback",
            "pump_running_feedback",
        ),
    )

    door1_open_sensor: DigitalInputStatus = Field(
        default_factory=DigitalInputStatus
    )

    door1_closed_sensor: DigitalInputStatus = Field(
        default_factory=lambda: DigitalInputStatus(state=True)
    )

    door2_open_sensor: DigitalInputStatus = Field(
        default_factory=DigitalInputStatus
    )

    door2_closed_sensor: DigitalInputStatus = Field(
        default_factory=lambda: DigitalInputStatus(state=True)
    )

    # Compatibility for existing backend code.
    @property
    def pump_running_feedback(self) -> DigitalInputStatus:
        return self.dispenser_running_feedback

    @pump_running_feedback.setter
    def pump_running_feedback(self, value: DigitalInputStatus) -> None:
        self.dispenser_running_feedback = value


# ============================================================
# Outputs
# ============================================================

class DigitalOutputStatus(BaseModel):
    commanded_state: bool = False
    command_source: CommandSource = CommandSource.NoneSource


class MachineOutputs(BaseModel):
    dispenser_trigger: DigitalOutputStatus = Field(
        default_factory=DigitalOutputStatus
    )

    door1_open_output: DigitalOutputStatus = Field(
        default_factory=DigitalOutputStatus,
        validation_alias=AliasChoices(
            "door1_open_output",
            "actuator1",
        ),
    )

    door1_close_output: DigitalOutputStatus = Field(
        default_factory=DigitalOutputStatus,
        validation_alias=AliasChoices(
            "door1_close_output",
            "actuator2",
        ),
    )

    door2_open_output: DigitalOutputStatus = Field(
        default_factory=DigitalOutputStatus,
        validation_alias=AliasChoices(
            "door2_open_output",
            "actuator3",
        ),
    )

    door2_close_output: DigitalOutputStatus = Field(
        default_factory=DigitalOutputStatus,
        validation_alias=AliasChoices(
            "door2_close_output",
            "actuator4",
        ),
    )

    # Backward-compatible internal attribute names.
    @property
    def actuator1(self) -> DigitalOutputStatus:
        return self.door1_open_output

    @actuator1.setter
    def actuator1(self, value: DigitalOutputStatus) -> None:
        self.door1_open_output = value

    @property
    def actuator2(self) -> DigitalOutputStatus:
        return self.door1_close_output

    @actuator2.setter
    def actuator2(self, value: DigitalOutputStatus) -> None:
        self.door1_close_output = value

    @property
    def actuator3(self) -> DigitalOutputStatus:
        return self.door2_open_output

    @actuator3.setter
    def actuator3(self, value: DigitalOutputStatus) -> None:
        self.door2_open_output = value

    @property
    def actuator4(self) -> DigitalOutputStatus:
        return self.door2_close_output

    @actuator4.setter
    def actuator4(self, value: DigitalOutputStatus) -> None:
        self.door2_close_output = value


# ============================================================
# Output mismatch status
# ============================================================

class OutputMismatchStatus(BaseModel):
    any_mismatch: bool = False
    dispenser_trigger_mismatch: bool = False

    door1_open_output_mismatch: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "door1_open_output_mismatch",
            "actuator1_mismatch",
        ),
    )

    door1_close_output_mismatch: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "door1_close_output_mismatch",
            "actuator2_mismatch",
        ),
    )

    door2_open_output_mismatch: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "door2_open_output_mismatch",
            "actuator3_mismatch",
        ),
    )

    door2_close_output_mismatch: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "door2_close_output_mismatch",
            "actuator4_mismatch",
        ),
    )

    mismatch_due_to_simulation_suppression: bool = False
    reason: str = ""

    # Backward-compatible internal attribute names.
    @property
    def actuator1_mismatch(self) -> bool:
        return self.door1_open_output_mismatch

    @actuator1_mismatch.setter
    def actuator1_mismatch(self, value: bool) -> None:
        self.door1_open_output_mismatch = value

    @property
    def actuator2_mismatch(self) -> bool:
        return self.door1_close_output_mismatch

    @actuator2_mismatch.setter
    def actuator2_mismatch(self, value: bool) -> None:
        self.door1_close_output_mismatch = value

    @property
    def actuator3_mismatch(self) -> bool:
        return self.door2_open_output_mismatch

    @actuator3_mismatch.setter
    def actuator3_mismatch(self, value: bool) -> None:
        self.door2_open_output_mismatch = value

    @property
    def actuator4_mismatch(self) -> bool:
        return self.door2_close_output_mismatch

    @actuator4_mismatch.setter
    def actuator4_mismatch(self, value: bool) -> None:
        self.door2_close_output_mismatch = value


# ============================================================
# Snapshot models
# ============================================================

class CommandSnapshot(BaseModel):
    door1: CommandModel
    door2: CommandModel
    dispenser: CommandModel
    machine: CommandModel
    engineering: CommandModel


class MachineSnapshot(BaseModel):
    machine: MachineStatus
    engineering_status: EngineeringStatus
    inputs: MachineInputs
    outputs: MachineOutputs
    output_requests: MachineOutputs
    output_mismatch_status: OutputMismatchStatus
    commands: CommandSnapshot
    door1: DeviceStatus
    door2: DeviceStatus
    dispenser: DeviceStatus

    igus_axis: Optional[IgusAxisStatus] = Field(
        default=None,
        description=(
            "Reserved for the Prototype 2 igus_axis device. "
            "The final motion and status contract is pending PLC verification."
        ),
    )


# ============================================================
# API serialization
# ============================================================

def enum_to_api(value: IntEnum):
    names = {
        "NoneDevice": "None",
        "NoneCommand": "None",
        "NoneSource": "None",
        "NoneStatus": "None",
        "NoneResult": "None",
        "NoneFault": "None",
        "NoneReject": "None",
    }

    return {
        "value": int(value),
        "name": names.get(value.name, value.name),
    }


def serialize_api(obj: Any):
    if isinstance(obj, IntEnum):
        return enum_to_api(obj)

    if isinstance(obj, BaseModel):
        return serialize_api(obj.model_dump())

    if isinstance(obj, dict):
        return {
            key: serialize_api(value)
            for key, value in obj.items()
        }

    if isinstance(obj, list):
        return [
            serialize_api(value)
            for value in obj
        ]

    return obj


# Backward-compatible model names used by the existing project/tests.
DeviceCommandModel = CommandModel
MachineCommandModel = CommandModel