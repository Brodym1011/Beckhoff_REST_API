import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

try:
    from .models import DeviceTarget, MultiDeviceCommandRequest, MultiDeviceCommandResponse
except ImportError:  # pragma: no cover - supports direct script execution
    from models import DeviceTarget, MultiDeviceCommandRequest, MultiDeviceCommandResponse


class DeviceAdapter(Protocol):
    def communication_test(self, request: MultiDeviceCommandRequest) -> MultiDeviceCommandResponse: ...


@dataclass
class MockDeviceAdapter:
    target: DeviceTarget
    outcome: str = "success"
    delay_ms: int = 250

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
    def __init__(self) -> None:
        self._adapters: dict[DeviceTarget, DeviceAdapter] = {}

    def register(self, target: DeviceTarget, adapter: DeviceAdapter) -> None:
        self._adapters[target] = adapter

    def get(self, target: DeviceTarget) -> DeviceAdapter:
        try:
            return self._adapters[target]
        except KeyError as exc:
            raise LookupError("ADAPTER_NOT_REGISTERED") from exc


class CommandRouter:
    def __init__(self, registry: DeviceRegistry) -> None:
        self.registry = registry

    def route(self, request: MultiDeviceCommandRequest) -> MultiDeviceCommandResponse:
        return self.registry.get(request.target_device).communication_test(request)


registry = DeviceRegistry()
for target in DeviceTarget:
    registry.register(target, MockDeviceAdapter(target))

router = CommandRouter(registry)
