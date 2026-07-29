"""Customer-facing IPC for RESTful multi-device actions."""

import json
import os
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, ttk
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = os.getenv(
    "IPC_API_BASE_URL",
    "http://127.0.0.1:8000/api/v1",
).rstrip("/")
API_HEALTH_CHECK_INTERVAL_MS = 5000
BRANDING_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "ancera_branding_transparent.png"
)

DEVICE_OPTIONS = {
    "Flex": {
        "api_value": "flex",
        "devices": {"Flex 1": "flex_1", "Flex 2": "flex_2"},
        "actions": {"Dispense": "dispense", "Drop Tip": "drop_tip"},
    },
    "Arm": {
        "api_value": "arm",
        "devices": {
            "Static Arm": "static_arm",
            "Tracked Arm": "tracked_arm",
        },
        "actions": {
            "Grab Sample": "grab_sample",
            "Drop Sample": "drop_sample",
        },
    },
    "PLC": {
        "api_value": "plc",
        "devices": {"PLC": "plc"},
        "actions": {"Open Door": "open_door", "Close Door": "close_door"},
    },
}


# Build the RESTful URL for a selected device type, name, and action.
def build_action_url(
    api_base_url: str,
    device_type: str,
    device_name: str,
    action: str,
) -> str:
    """Build a URL-safe /device-type/device-name/action endpoint."""
    segments = (device_type, device_name, action)
    encoded = "/".join(quote(segment, safe="") for segment in segments)
    return f"{api_base_url.rstrip('/')}/{encoded}"


# Build the system-health URL from the user-selected API base URL.
def build_health_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/system"


# Query the API heartbeat and convert failures into customer-readable text.
def check_api_health(api_base_url: str, opener=urlopen) -> tuple[bool, str]:
    """Check API availability and return a UI-safe status message."""
    try:
        with opener(build_health_url(api_base_url), timeout=3) as response:
            result = json.loads(response.read().decode())
        if result.get("heartbeat") is True:
            return True, "API Connected"
        return False, "Unable to connect to the API: unhealthy response"
    except Exception:
        return False, "Unable to connect to the API. Make sure the API is running."


# Format the important API response fields for display in the GUI log.
def format_action_response(result: dict) -> str:
    """Format the routed fields so they are explicit in the IPC log."""
    return (
        f"device_type={result.get('device_type', 'unknown')} | "
        f"device_name={result.get('device_name', 'unknown')} | "
        f"action={result.get('action', 'unknown')} | "
        f"status={result.get('status', 'unknown')} | "
        f"message={result.get('message', 'Unknown response')}"
    )


class FakeIPC(tk.Tk):
    # Initialize window state, selector values, layout, and health monitoring.
    def __init__(self) -> None:
        super().__init__()
        self.title("Multi-Device Demo")
        self.geometry("1280x720")
        self.minsize(1000, 600)
        self.configure(bg="#f4f5f7")

        self.device_type = tk.StringVar(value="Flex")
        self.device_name = tk.StringVar()
        self.action = tk.StringVar()
        self.api_base_url = tk.StringVar(value=DEFAULT_API_BASE_URL)
        self._build()
        self._refresh_options()
        self._schedule_api_check(immediate=True)

    # Construct all visible GUI controls and arrange the dashboard layout.
    def _build(self) -> None:
        root = tk.Frame(self, bg="#f4f5f7", padx=48, pady=28)
        root.pack(fill="both", expand=True)

        header = tk.Frame(root, bg="#f4f5f7")
        header.pack(fill="x", pady=(0, 24))
        for column in range(3):
            header.grid_columnconfigure(column, weight=1, uniform="header")

        if BRANDING_PATH.exists():
            self.branding_image = tk.PhotoImage(file=str(BRANDING_PATH)).subsample(8, 8)
            tk.Label(
                header,
                image=self.branding_image,
                bg="#f4f5f7",
                bd=0,
            ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="Multi-Device Demo",
            font=("Segoe UI", 28, "bold"),
            bg="#f4f5f7",
            fg="#20242a",
        ).grid(row=0, column=1)

        connection = tk.Frame(header, bg="#f4f5f7")
        connection.grid(row=0, column=2, sticky="e")
        self.api_status_label = tk.Label(
            connection,
            text="●  API Checking",
            font=("Segoe UI", 11, "bold"),
            bg="#f4f5f7",
            fg="#b42318",
        )
        self.api_status_label.pack(anchor="e")
        self.api_tip_label = tk.Label(
            connection,
            text="Unable to connect to the API. Checking connection...",
            font=("Segoe UI", 9),
            bg="#f4f5f7",
            fg="#7a271a",
            wraplength=260,
            justify="right",
        )
        self.api_tip_label.pack(anchor="e", pady=(3, 0))

        tk.Button(
            root,
            text="Run Demo",
            state="disabled",
            font=("Segoe UI", 14, "bold"),
            relief="solid",
            bd=1,
            disabledforeground="#666",
            height=1,
        ).pack(fill="x", pady=(0, 16), ipady=5)

        action_panel = tk.Frame(
            root,
            bg="white",
            highlightbackground="#c7cbd1",
            highlightthickness=1,
            padx=28,
            pady=22,
        )
        action_panel.pack(fill="x")
        for column in range(3):
            action_panel.grid_columnconfigure(column, weight=1, uniform="selector")

        self.type_combo = self._selector(
            action_panel,
            0,
            "Device Type",
            self.device_type,
            tuple(DEVICE_OPTIONS),
        )
        self.name_combo = self._selector(action_panel, 1, "Device Name", self.device_name, ())
        self.action_combo = self._selector(action_panel, 2, "Action", self.action, ())
        self.type_combo.bind("<<ComboboxSelected>>", self._refresh_options)

        self.execute_button = tk.Button(
            action_panel,
            text="Execute Action",
            command=self.execute_action,
            bg="#064887",
            fg="white",
            activebackground="#0b5aa4",
            activeforeground="white",
            font=("Segoe UI", 14, "bold"),
            relief="flat",
            cursor="hand2",
            height=2,
        )
        self.execute_button.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=(18, 0))

        self.status_label = tk.Label(
            action_panel,
            text="Ready",
            font=("Segoe UI", 12, "bold"),
            bg="white",
            fg="#15912a",
        )
        self.status_label.grid(row=3, column=0, columnspan=3, pady=(10, 0))

        title_row = tk.Frame(root, bg="#f4f5f7")
        title_row.pack(fill="x", pady=(22, 8))
        tk.Label(
            title_row,
            text="API Responses",
            font=("Segoe UI", 15, "bold"),
            bg="#f4f5f7",
            fg="#20242a",
        ).pack(side="left")
        tk.Button(
            title_row,
            text="Clear Log",
            command=self.clear_log,
            fg="#064887",
            font=("Segoe UI", 11, "bold"),
            relief="solid",
            bd=1,
            padx=16,
        ).pack(side="right")

        endpoint_frame = tk.Frame(root, bg="#f4f5f7")
        endpoint_frame.pack(side="bottom", fill="x", pady=(12, 0))
        tk.Label(
            endpoint_frame,
            text="API Endpoint Base URL",
            font=("Segoe UI", 10, "bold"),
            bg="#f4f5f7",
            fg="#30343a",
        ).pack(side="left", padx=(0, 10))
        self.api_url_entry = tk.Entry(
            endpoint_frame,
            textvariable=self.api_base_url,
            font=("Consolas", 10),
            relief="solid",
            bd=1,
        )
        self.api_url_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.api_url_entry.bind("<Return>", lambda _event: self._start_api_check())
        tk.Button(
            endpoint_frame,
            text="Check Connection",
            command=self._start_api_check,
            fg="#064887",
            font=("Segoe UI", 9, "bold"),
            relief="solid",
            bd=1,
            padx=12,
        ).pack(side="left", padx=(10, 0), ipady=2)

        self.log = scrolledtext.ScrolledText(
            root,
            height=16,
            font=("Consolas", 11),
            relief="solid",
            bd=1,
            wrap="word",
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)

    # Create one labeled, read-only dropdown used by the action selectors.
    def _selector(self, parent, column, label, variable, values):
        frame = tk.Frame(parent, bg="white", padx=8)
        frame.grid(row=0, column=column, sticky="ew")
        tk.Label(
            frame,
            text=label,
            font=("Segoe UI", 11, "bold"),
            bg="white",
            fg="#30343a",
        ).pack(anchor="w", pady=(0, 6))
        combo = ttk.Combobox(
            frame,
            textvariable=variable,
            values=values,
            state="readonly",
            font=("Segoe UI", 12),
        )
        combo.pack(fill="x", ipady=5)
        return combo

    # Refresh device names and actions when the selected device type changes.
    def _refresh_options(self, _event=None) -> None:
        options = DEVICE_OPTIONS[self.device_type.get()]
        device_names = tuple(options["devices"])
        actions = tuple(options["actions"])
        self.name_combo.configure(values=device_names)
        self.action_combo.configure(values=actions)
        self.device_name.set(device_names[0])
        self.action.set(actions[0])

    # Queue an immediate or delayed API availability check on the Tk event loop.
    def _schedule_api_check(self, immediate: bool = False) -> None:
        delay = 0 if immediate else API_HEALTH_CHECK_INTERVAL_MS
        self.after(delay, self._start_api_check)

    # Start a non-blocking health-check worker using the URL shown in the GUI.
    def _start_api_check(self) -> None:
        api_base_url = self.api_base_url.get().strip()
        if not api_base_url:
            self._set_api_status(False, "Unable to connect to the API. Enter an API URL.")
            return
        threading.Thread(
            target=self._check_api,
            args=(api_base_url,),
            daemon=True,
        ).start()

    # Perform the network health check outside the GUI thread.
    def _check_api(self, api_base_url: str) -> None:
        available, message = check_api_health(api_base_url)
        try:
            self.after(0, self._set_api_status, available, message)
        except tk.TclError:
            pass

    # Update the green or red API indicator and schedule the next check.
    def _set_api_status(self, available: bool, message: str) -> None:
        if available:
            self.api_status_label.configure(text="●  API Connected", fg="#15912a")
            self.api_tip_label.configure(text="", fg="#15912a")
        else:
            self.api_status_label.configure(text="●  API Unavailable", fg="#b42318")
            self.api_tip_label.configure(text=message, fg="#7a271a")
        self._schedule_api_check()

    # Remove all existing entries from the API response log.
    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # Append a timestamped route and message to the response log.
    def write_log(self, route: str, message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {route} - {message}\n"
        self.log.configure(state="normal")
        self.log.insert("end", line)
        self.log.see("end")
        self.log.configure(state="disabled")

    # Resolve the selected values and launch the requested action asynchronously.
    def execute_action(self) -> None:
        options = DEVICE_OPTIONS[self.device_type.get()]
        device_type = options["api_value"]
        device_name = options["devices"][self.device_name.get()]
        action = options["actions"][self.action.get()]
        route = f"{device_type}/{device_name}/{action}"
        api_base_url = self.api_base_url.get().strip()
        if not api_base_url:
            self._set_api_status(False, "Unable to connect to the API. Enter an API URL.")
            return

        self.execute_button.configure(state="disabled")
        self.status_label.configure(text="In Progress", fg="#c47b00")
        self.write_log(route, "Request sent")
        threading.Thread(
            target=self._request,
            args=(api_base_url, device_type, device_name, action),
            daemon=True,
        ).start()

    # POST the selected action to the REST API and normalize network failures.
    def _request(
        self,
        api_base_url: str,
        device_type: str,
        device_name: str,
        action: str,
    ) -> None:
        url = build_action_url(api_base_url, device_type, device_name, action)
        route = f"{device_type}/{device_name}/{action}"
        try:
            request = Request(url, data=b"", method="POST")
            with urlopen(request, timeout=12) as response:
                result = json.loads(response.read().decode())
            response_route = "/".join(
                (
                    result.get("device_type", device_type),
                    result.get("device_name", device_name),
                    result.get("action", action),
                )
            )
            self.after(
                0,
                self._finish,
                response_route,
                result.get("status", "failed"),
                format_action_response(result),
            )
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            self.after(0, self._finish, route, "failed", f"API error {exc.code}: {detail}")
        except (URLError, TimeoutError) as exc:
            self.after(0, self._finish, route, "failed", f"API unavailable: {exc}")
        except Exception as exc:
            self.after(0, self._finish, route, "failed", f"Request failed: {exc}")

    # Restore the Execute button and present the action's terminal result.
    def _finish(self, route: str, status: str, message: str) -> None:
        colors = {
            "completed": "#15912a",
            "timed_out": "#b35a00",
            "failed": "#b42318",
        }
        labels = {
            "completed": "Successful",
            "timed_out": "Timed Out",
            "failed": "Failed",
        }
        self.status_label.configure(
            text=labels.get(status, status.title()),
            fg=colors.get(status, "#b42318"),
        )
        self.execute_button.configure(state="normal")
        self.write_log(route, message)


if __name__ == "__main__":
    FakeIPC().mainloop()
