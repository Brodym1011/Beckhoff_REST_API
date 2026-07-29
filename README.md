# Beckhoff REST API and Desktop IPC

## Requirements

- Windows, macOS, or Linux with a graphical desktop
- Python 3.10 or newer

Run all commands from the project root.

## Install

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, install and run directly
through its Python executable:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On minimal Debian or Ubuntu installations, install the Qt runtime libraries:

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libxkbcommon-x11-0
```

## Start

The API and desktop IPC run as separate applications. Keep both terminals
open.

### Terminal 1: API

Activate the virtual environment, then run:

```bash
python -m uvicorn source.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

### Terminal 2: desktop IPC

Activate the same virtual environment in a second terminal, then run:

```bash
python fake_ipc.py
```

The IPC defaults to `http://127.0.0.1:8000/api/v1`. The endpoint can be
changed in the URL field at the bottom of the desktop window.

### Commands without activation on Windows

```powershell
.\.venv\Scripts\python.exe -m uvicorn source.main:app --reload --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
.\.venv\Scripts\python.exe fake_ipc.py
```
