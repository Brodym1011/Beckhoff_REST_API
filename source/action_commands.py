import json
import logging
import os
import subprocess
from pathlib import Path

_DEFAULT_CONFIG = Path(__file__).parent.parent / "action_commands.json"

_log = logging.getLogger(__name__)


def _load_config() -> dict[str, list[str]]:
    path = Path(os.getenv("ACTION_COMMANDS_FILE", str(_DEFAULT_CONFIG)))
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


def run_action_command(action: str) -> tuple[bool, str] | None:
    """Run the command list mapped to action without invoking a shell.

    Returns None if no mapping exists, or (success, message) otherwise.
    """
    command = _load_config().get(action)
    if command is None:
        _log.debug("action=%s has no command mapping, falling through to mock", action)
        return None

    _log.info("action=%s command=%s", action, command)
    result = subprocess.run(
        command,
        shell=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _log.info("action=%s returncode=%d", action, result.returncode)
    if result.stdout:
        _log.debug("action=%s stdout=%r", action, result.stdout.strip())
    if result.stderr:
        _log.warning("action=%s stderr=%r", action, result.stderr.strip())

    if result.returncode == 0:
        return True, result.stdout.strip() or f"{action} completed"
    output = (result.stderr or result.stdout).strip()
    return False, output or f"{action} failed (exit {result.returncode})"
