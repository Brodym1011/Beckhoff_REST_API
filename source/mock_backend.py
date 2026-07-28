import threading, time
from models import *
from mock_data import *

class MockBackend:
    def __init__(self):
        self._lock=threading.RLock(); self.machine_status=machine_status; self.engineering_status=engineering_status
        self.inputs=inputs; self.outputs=outputs; self.output_requests=output_requests; self.output_mismatch_status=output_mismatch_status
        self.door1_status=door1_status; self.door2_status=door2_status; self.dispenser_status=dispenser_status
        self.commands=commands; self.machine_command=machine_command; self.engineering_command=engineering_command
    def get_system_status(self): return system_status
    def get_machine_status(self): return self.machine_status
    def get_machine_outputs(self): return self.outputs
    def get_door1_status(self): return self.door1_status
    def get_door2_status(self): return self.door2_status
    def get_dispenser_status(self): return self.dispenser_status
    def get_all_devices(self): return [self.door1_status,self.door2_status,self.dispenser_status]
    def get_door1_command(self): return self.commands['door1']
    def get_door2_command(self): return self.commands['door2']
    def get_dispenser_command(self): return self.commands['dispenser']
    def get_machine_command(self): return self.machine_command
    def get_engineering_command(self): return self.engineering_command
    def get_snapshot(self):
        self._refresh_snapshot()
        return MachineSnapshot(machine=self.machine_status,engineering_status=self.engineering_status,inputs=self.inputs,outputs=self.outputs,
            output_requests=self.output_requests,output_mismatch_status=self.output_mismatch_status,
            commands=CommandSnapshot(door1=self.commands['door1'],door2=self.commands['door2'],dispenser=self.commands['dispenser'],machine=self.machine_command,engineering=self.engineering_command),
            door1=self.door1_status,door2=self.door2_status,dispenser=self.dispenser_status)
    def _reject(self, command, request, code, message):
        command.execute=False; command.command=request.command; command.source=request.source; command.request_id=request.request_id
        command.status=CommandStatus.Rejected; command.status_message=message; command.accepted=False; command.completed=True
        command.result=CommandResult.Rejected; command.reject_code=code; return command
    def _start(self, command, request, message):
        if request.request_id<=0: return self._reject(command,request,CommandRejectCode.InvalidRequestID,'Invalid Request ID')
        if request.source==CommandSource.NoneSource: return self._reject(command,request,CommandRejectCode.InvalidCommandSource,'Invalid Command Source')
        command.execute=True; command.command=request.command; command.source=request.source; command.request_id=request.request_id
        command.status=CommandStatus.Received; command.status_message=message; command.parameter1=getattr(request,'parameter1',None); command.parameter2=getattr(request,'parameter2',None)
        command.accepted=True; command.completed=False; command.result=CommandResult.Accepted; command.reject_code=CommandRejectCode.NoneReject
        return command
    def _lifecycle(self, key, device=None, action=None):
        cmd=self.commands[key] if key in self.commands else getattr(self,f'{key}_command'); rid=cmd.request_id
        def run():
            for st in (CommandStatus.Pending,CommandStatus.Accepted,CommandStatus.Executing):
                time.sleep(.15)
                with self._lock:
                    if cmd.request_id!=rid:return
                    cmd.status=st; cmd.status_message=f'{key.title()} command {st.name.lower()}'
            time.sleep(.2)
            with self._lock:
                if cmd.request_id!=rid:return
                if action: action()
                cmd.execute=False; cmd.status=CommandStatus.Complete; cmd.status_message=f'{key.title()} command complete'; cmd.completed=True; cmd.result=CommandResult.Complete; cmd.last_completed_request_id=rid
                if device:
                    device.state=DeviceState.Complete; device.busy=False; device.active_request_id=0; device.last_completed_request_id=rid; device.cycle_count+=1
                self._refresh_snapshot()
        threading.Thread(target=run,daemon=True).start()
    def _submit_device(self,key,request):
        with self._lock:
            cmd=self.commands[key]; device={'door1':self.door1_status,'door2':self.door2_status,'dispenser':self.dispenser_status}[key]
            self._start(cmd,request,f'{key.title()} command received')
            if not cmd.accepted:return cmd
            device.state=DeviceState.Commanded; device.busy=True; device.active_request_id=request.request_id
            def action():
                if key.startswith('door'):
                    if request.command==DeviceCommand.Open: device.position=DoorPosition.Open; device.open_sensor_active=True; device.closed_sensor_active=False
                    elif request.command==DeviceCommand.Close: device.position=DoorPosition.Closed; device.open_sensor_active=False; device.closed_sensor_active=True
                    elif request.command==DeviceCommand.ResetFault: device.fault_active=False; device.fault_code=FaultCode.NoneFault
                elif request.command==DeviceCommand.ResetFault: device.fault_active=False; device.fault_code=FaultCode.NoneFault
            self._lifecycle(key,device,action); return cmd
    def submit_door1_command(self,r): return self._submit_device('door1',r)
    def submit_door2_command(self,r): return self._submit_device('door2',r)
    def submit_dispenser_command(self,r): return self._submit_device('dispenser',r)
    def submit_machine_command(self,r):
        with self._lock:
            self._start(self.machine_command,r,'Machine command received')
            if self.machine_command.accepted:
                def action():
                    if r.command==MachineCommand.ClearLastFault: self.machine_status.last_fault=FaultCode.NoneFault; self.machine_status.last_fault_device=DeviceID.NoneDevice
                self._lifecycle('machine',action=action)
            return self.machine_command
    def submit_engineering_command(self,r):
        with self._lock:
            self._start(self.engineering_command,r,'Engineering command received')
            if not self.engineering_command.accepted:return self.engineering_command
            def action(): self._apply_engineering(r)
            self._lifecycle('engineering',action=action); return self.engineering_command
    def _bool_param(self,v): return bool(int(v or 0))
    def _apply_engineering(self,r):
        c=r.command; e=self.engineering_status
        if c==EngineeringCommand.EnableSimulationMode:e.simulation_mode=True
        elif c==EngineeringCommand.DisableSimulationMode:e.simulation_mode=False
        elif c==EngineeringCommand.EnableOutputSuppression:e.suppress_physical_outputs_in_simulation=True
        elif c==EngineeringCommand.DisableOutputSuppression:e.suppress_physical_outputs_in_simulation=False
        elif c==EngineeringCommand.ClearSimulatedInputs:
            e.sim_pump_running_feedback=e.sim_door1_open_sensor=e.sim_door1_closed_sensor=e.sim_door2_open_sensor=e.sim_door2_closed_sensor=False
        elif c==EngineeringCommand.SetSimPumpRunningFeedback:e.sim_pump_running_feedback=self._bool_param(r.parameter1)
        elif c==EngineeringCommand.SetSimDoor1OpenSensor:e.sim_door1_open_sensor=self._bool_param(r.parameter1)
        elif c==EngineeringCommand.SetSimDoor1ClosedSensor:e.sim_door1_closed_sensor=self._bool_param(r.parameter1)
        elif c==EngineeringCommand.SetSimDoor2OpenSensor:e.sim_door2_open_sensor=self._bool_param(r.parameter1)
        elif c==EngineeringCommand.SetSimDoor2ClosedSensor:e.sim_door2_closed_sensor=self._bool_param(r.parameter1)
        elif c in (EngineeringCommand.SetSimDoor1Position,EngineeringCommand.SetSimDoor2Position):
            p=int(r.parameter1 if r.parameter1 is not None else -1)
            if p not in (0,1,2,3):
                self.engineering_command.status=CommandStatus.Rejected; self.engineering_command.result=CommandResult.Rejected; self.engineering_command.reject_code=CommandRejectCode.InvalidSimulatedSensorState; self.engineering_command.accepted=False; return
            o,cl={0:(False,False),1:(False,True),2:(True,False),3:(True,True)}[p]
            if c==EngineeringCommand.SetSimDoor1Position:e.sim_door1_open_sensor=o;e.sim_door1_closed_sensor=cl
            else:e.sim_door2_open_sensor=o;e.sim_door2_closed_sensor=cl
        self._refresh_snapshot()
    def _refresh_snapshot(self):
        e=self.engineering_status; m=self.machine_status
        m.simulation_mode=e.simulation_mode; m.suppress_physical_outputs_in_simulation=e.suppress_physical_outputs_in_simulation
        m.physical_outputs_suppressed=e.simulation_mode and e.suppress_physical_outputs_in_simulation; e.physical_outputs_suppressed=m.physical_outputs_suppressed
        if e.simulation_mode:
            self.inputs.pump_running_feedback.state=e.sim_pump_running_feedback; self.inputs.door1_open_sensor.state=e.sim_door1_open_sensor; self.inputs.door1_closed_sensor.state=e.sim_door1_closed_sensor
            self.inputs.door2_open_sensor.state=e.sim_door2_open_sensor; self.inputs.door2_closed_sensor.state=e.sim_door2_closed_sensor
        for dev,op,cl in ((self.door1_status,self.inputs.door1_open_sensor.state,self.inputs.door1_closed_sensor.state),(self.door2_status,self.inputs.door2_open_sensor.state,self.inputs.door2_closed_sensor.state)):
            dev.open_sensor_active=op; dev.closed_sensor_active=cl; dev.position=DoorPosition.Fault if op and cl else DoorPosition.Open if op else DoorPosition.Closed if cl else DoorPosition.Unknown
        m.busy=any(d.busy for d in (self.door1_status,self.door2_status,self.dispenser_status)); m.fault=any(d.fault_active for d in (self.door1_status,self.door2_status,self.dispenser_status)); m.ready=not m.busy and not m.fault
        names=('dispenser_trigger','actuator1','actuator2','actuator3','actuator4'); mism=[]
        for n in names:
            req=getattr(self.output_requests,n); out=getattr(self.outputs,n)
            out.commanded_state=False if m.physical_outputs_suppressed else req.commanded_state; out.command_source=req.command_source; mism.append(req.commanded_state!=out.commanded_state)
        ms=self.output_mismatch_status; ms.dispenser_trigger_mismatch,ms.actuator1_mismatch,ms.actuator2_mismatch,ms.actuator3_mismatch,ms.actuator4_mismatch=mism
        ms.any_mismatch=any(mism); ms.mismatch_due_to_simulation_suppression=ms.any_mismatch and m.physical_outputs_suppressed; ms.reason='Physical outputs suppressed during simulation' if ms.mismatch_due_to_simulation_suppression else ('Requested and physical outputs differ' if ms.any_mismatch else '')

backend=MockBackend()
