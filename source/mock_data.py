try:
    from .models import *
except ImportError:  # pragma: no cover - supports direct script execution
    from models import *

machine_status=MachineStatus()
engineering_status=EngineeringStatus()
inputs=MachineInputs()
outputs=MachineOutputs()
output_requests=MachineOutputs()
output_mismatch_status=OutputMismatchStatus()
door1_status=DeviceStatus(device_id=DeviceID.Door1,position=DoorPosition.Closed,closed_sensor_active=True)
door2_status=DeviceStatus(device_id=DeviceID.Door2,position=DoorPosition.Closed,closed_sensor_active=True)
dispenser_status=DeviceStatus(device_id=DeviceID.Dispenser)
commands={"door1":CommandModel(command=DeviceCommand.NoneCommand),"door2":CommandModel(command=DeviceCommand.NoneCommand),"dispenser":CommandModel(command=DeviceCommand.NoneCommand)}
machine_command=CommandModel(command=MachineCommand.NoneCommand)
engineering_command=CommandModel(command=EngineeringCommand.NoneCommand)
system_status={"api_version":"1.1","project_version":"mock","heartbeat":True}
