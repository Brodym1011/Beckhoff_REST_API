# Beckhoff PLC REST API

This project exposes a FastAPI service for interacting with a Beckhoff PLC-oriented machine model.

## Prerequisites

- Python 3.9 or newer

Create and activate a virtual environment if you want an isolated setup:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

## Run the API

Source code lives in the `source/` directory.

From the project root, start the service directly:

```bash
python -m uvicorn source.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- http://127.0.0.1:8000/docs for Swagger UI
- http://127.0.0.1:8000/redoc for ReDoc

## Run tests

Make sure the project dependencies are installed:

```bash
pip install -r requirements.txt
```

Then run the unit tests from the project root:

```bash
python -m pytest -q
```

For full pytest output, use:

```bash
python -m pytest
```

## Stop the API

If the API was started in a shell, stop it with Ctrl+C.

For background runs, use the process manager of your shell or OS.

## Backend configuration

The application defaults to the mock backend:

```bash
set BACKEND_MODE=mock
```

On Windows PowerShell, use:

```powershell
$env:BACKEND_MODE="mock"
```

The `ads` backend is reserved for future implementation and will raise an error if selected.

## Example endpoint

A basic health/status endpoint is available at:

```bash
curl http://127.0.0.1:8000/api/v1/system
```
