import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

try:
    from .models import (
        DeviceActionResponse,
        DeviceTarget,
        DeviceType,
        MultiDeviceCommandRequest,
        MultiDeviceCommandResponse,
    )
except ImportError:  # pragma: no cover - supports direct script execution
    from models import (
        DeviceActionResponse,
        DeviceTarget,
        DeviceType,
        MultiDeviceCommandRequest,
        MultiDeviceCommandResponse,
    )


DEVICE_NAMES = {
    DeviceType.flex: {
        "flex_1": DeviceTarget.flex_1,
        "flex_2": DeviceTarget.flex_2,
    },
    DeviceType.arm: {
        "static_arm": DeviceTarget.static_arm,
        "tracked_arm": DeviceTarget.tracked_arm,
    },
    DeviceType.plc: {
        "plc": DeviceTarget.plc,
    },
}

DEVICE_ACTIONS = {
    DeviceType.flex: {"dispense", "drop_tip"},
    DeviceType.arm: {"grab_sample", "drop_sample"},
    DeviceType.plc: {"open_door", "close_door"},
}


class DeviceAdapter(Protocol):
    # Define the communication-test operation required from every adapter.
    def communication_test(self, request: MultiDeviceCommandRequest) -> MultiDeviceCommandResponse: ...


@dataclass
class MockDeviceAdapter:
    target: DeviceTarget
    outcome: str = "success"
    delay_ms: int = 250

    # Simulate a communication check and return the shared legacy response model.
    def communication_test(self, request: MultiDeviceCommandRequest) -> MultiDeviceCommandResponse:
        outcome = os.getenv(f"MOCK_{self.target.value.upper()}_OUTCOME", self.outcome).lower()
        delay_ms = int(os.getenv(f"MOCK_{self.target.value.upper()}_DELAY_MS", self.delay_ms))
        if outcome == "timeout":
            delay_ms = request.timeout_ms + 1
        time.sleep(min(delay_ms, request.timeout_ms) / 1000)

        status, accepted, message, error_code = {
            "success": ("completed", True, "Communication successful", None),
            "failure": ("failed", True, "Communication failed", "INTERNAL_ROUTING_ERROR"),
            "unavailable": ("failed", True, "Device unavailable", "DEVICE_UNAVAILABLE"),
            "timeout": ("timed_out", True, "Communication timed out", "DEVICE_TIMEOUT"),
        }.get(outcome, ("failed", True, "Communication failed", "INTERNAL_ROUTING_ERROR"))

        return MultiDeviceCommandResponse(
            request_id=request.request_id,
            target_device=request.target_device,
            status=status,
            accepted=accepted,
            message=message,
            error_code=error_code,
            completed_at=datetime.now(timezone.utc),
        )


class DeviceRegistry:
    # Create an empty target-to-adapter lookup table.
    def __init__(self) -> None:
        self._adapters: dict[DeviceTarget, DeviceAdapter] = {}

    # Associate a supported device target with its adapter implementation.
    def register(self, target: DeviceTarget, adapter: DeviceAdapter) -> None:
        self._adapters[target] = adapter

    # Return the adapter for a target or report that it is not registered.
    def get(self, target: DeviceTarget) -> DeviceAdapter:
        try:
            return self._adapters[target]
        except KeyError as exc:
            raise LookupError("ADAPTER_NOT_REGISTERED") from exc


class CommandRouter:
    # Store the registry used for all command and action routing.
    def __init__(self, registry: DeviceRegistry) -> None:
        self.registry = registry

    # Route a legacy communication-test envelope to its target adapter.
    def route(self, request: MultiDeviceCommandRequest) -> MultiDeviceCommandResponse:
        return self.registry.get(request.target_device).communication_test(request)

    # Validate and execute a RESTful action for a named device.
    def route_action(
        self,
        device_type: DeviceType,
        device_name: str,
        action: str,
    ) -> DeviceActionResponse:
        target = DEVICE_NAMES.get(device_type, {}).get(device_name)
        if target is None:
            raise LookupError("UNKNOWN_DEVICE")
        if action not in DEVICE_ACTIONS[device_type]:
            raise ValueError("UNSUPPORTED_ACTION")

        adapter = self.registry.get(target)
        outcome = os.getenv(
            f"MOCK_{target.value.upper()}_OUTCOME",
            getattr(adapter, "outcome", "success"),
        ).lower()
        delay_ms = int(os.getenv(
            f"MOCK_{target.value.upper()}_DELAY_MS",
            getattr(adapter, "delay_ms", 250),
        ))
        time.sleep(max(delay_ms, 0) / 1000)

        status, accepted, message, error_code = {
            "success": ("completed", True, f"{action.replace('_', ' ').title()} completed", None),
            "failure": ("failed", True, f"{action.replace('_', ' ').title()} failed", "ACTION_FAILED"),
            "unavailable": ("failed", False, "Device unavailable", "DEVICE_UNAVAILABLE"),
            "timeout": ("timed_out", True, "Action timed out", "DEVICE_TIMEOUT"),
        }.get(outcome, ("failed", False, "Action failed", "INTERNAL_ROUTING_ERROR"))

        return DeviceActionResponse(
            device_type=device_type,
            device_name=device_name,
            action=action,
            status=status,
            accepted=accepted,
            message=message,
            request_id=str(uuid4()),
            error_code=error_code,
            completed_at=datetime.now(timezone.utc),
        )


registry = DeviceRegistry()
for target in DeviceTarget:
    registry.register(target, MockDeviceAdapter(target))

router = CommandRouter(registry)
