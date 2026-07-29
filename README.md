# Beckhoff REST API and Multi-Device Demo IPC

This project contains:

- A FastAPI service for the existing Beckhoff PLC-oriented machine model.
- A multi-device command endpoint that routes communication tests to mock adapters.
- A customer-facing Python/Tkinter IPC for testing Flex 1, Flex 2, PLC, Static Arm, and Tracked Arm.

The IPC displays the transparent Ancera branding from
`assets/ancera_branding_transparent.png` in the upper-left corner.

The **Run Demo** button is intentionally disabled. Demo sequencing is not part of the current task.

## Requirements

- Windows with Python 3.9 or newer
- Tkinter, which is included with the standard Python installer for Windows

All commands below must be run from the project root:

```text
C:\Users\bminnocci\Documents\code\Beckhoff_REST_API
```

## First-time setup

Open PowerShell in the project root and create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents activation, the environment can be used without activating it:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Start the demo

The API and IPC are separate applications. Keep both terminals open while using the demo.

### Terminal 1: start the API

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn source.main:app --reload --host 127.0.0.1 --port 8000
```

Without activating the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn source.main:app --reload --host 127.0.0.1 --port 8000
```

Wait until the terminal reports that Uvicorn is running. The API is then available at:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- System status: http://127.0.0.1:8000/api/v1/system

### Terminal 2: start the fake IPC

Open another PowerShell window in the same project root:

```powershell
.\.venv\Scripts\Activate.ps1
python fake_ipc.py
```

Without activating the virtual environment:

```powershell
.\.venv\Scripts\python.exe fake_ipc.py
```

The **Test Flex 1**, **Test Flex 2**, **Test PLC**, **Test Static Arm**, and **Test Tracked Arm** buttons submit requests to:

```text
POST http://127.0.0.1:8000/api/v1/commands
```

The selected button is disabled while its request is running. Its status and the final API message are shown in the IPC window.

## Configure mock results

Each target defaults to `success`. Set an outcome in the API terminal before starting Uvicorn to demonstrate another result:

```powershell
$env:MOCK_FLEX_1_OUTCOME="unavailable"
$env:MOCK_FLEX_2_OUTCOME="failure"
$env:MOCK_PLC_OUTCOME="timeout"
$env:MOCK_STATIC_ARM_OUTCOME="success"
$env:MOCK_TRACKED_ARM_OUTCOME="success"
python -m uvicorn source.main:app --reload --host 127.0.0.1 --port 8000
```

Supported values are:

- `success`
- `failure`
- `unavailable`
- `timeout`

Optional simulated adapter delay values can also be configured in milliseconds:

```powershell
$env:MOCK_FLEX_1_DELAY_MS="1500"
```

Environment variables apply only to the PowerShell window in which they are set.

## Use a different API address

The IPC defaults to `http://127.0.0.1:8000/api/v1/commands`. To use another address, set `IPC_API_URL` in the IPC terminal before starting the GUI:

```powershell
$env:IPC_API_URL="http://192.168.1.50:8000/api/v1/commands"
python fake_ipc.py
```

## Run tests

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

The tests cover the existing PLC API and routing for all five multi-device targets.

## Stop the applications

- Close the IPC window to stop the GUI.
- Press `Ctrl+C` in the API terminal to stop Uvicorn.

## Troubleshooting

### The IPC reports that the API is unavailable

Confirm that Terminal 1 is still running and open http://127.0.0.1:8000/docs in a browser. Also check that `IPC_API_URL` points to the `/api/v1/commands` endpoint.

### `python` is not recognized

Install Python from python.org with **Add Python to PATH** enabled, or use the Python launcher (`py`) in place of `python`.

### Tkinter is missing

Re-run the standard Windows Python installer, choose **Modify**, and enable **Tcl/Tk and IDLE**.

## Existing backend configuration

The PLC-oriented application defaults to its mock backend. It can be selected explicitly before starting the API:

```powershell
$env:BACKEND_MODE="mock"
```

The `ads` backend is reserved for future implementation and currently raises an error if selected.
