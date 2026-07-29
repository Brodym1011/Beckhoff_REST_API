"""Simple customer-facing IPC for the multi-device communication demo."""

import json
import os
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import scrolledtext
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


API_URL = os.getenv("IPC_API_URL", "http://127.0.0.1:8000/api/v1/commands")
BRANDING_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "ancera_branding_transparent.png"
)
DEVICES = (
    ("flex_1", "Flex 1"),
    ("flex_2", "Flex 2"),
    ("plc", "PLC"),
    ("static_arm", "Static Arm"),
    ("tracked_arm", "Tracked Arm"),
)


def build_command_payload(target: str, timeout_ms: int = 10000) -> dict:
    """Build the standard command envelope sent by every IPC test button."""
    return {
        "request_id": str(uuid4()),
        "target_device": target,
        "command": "communication_test",
        "parameters": {},
        "source": "fake_ipc",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timeout_ms": timeout_ms,
    }


class FakeIPC(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Multi-Device Demo")
        self.geometry("1280x720")
        self.minsize(1000, 600)
        self.configure(bg="#f4f5f7")
        self.buttons: dict[str, tk.Button] = {}
        self.statuses: dict[str, tk.Label] = {}
        self._build()

    def _build(self) -> None:
        root = tk.Frame(self, bg="#f4f5f7", padx=48, pady=28)
        root.pack(fill="both", expand=True)

        header = tk.Frame(root, bg="#f4f5f7")
        header.pack(fill="x", pady=(0, 24))
        header.grid_columnconfigure(0, weight=1, uniform="header")
        header.grid_columnconfigure(1, weight=1, uniform="header")
        header.grid_columnconfigure(2, weight=1, uniform="header")

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

        tk.Button(root, text="Run Demo", state="disabled", font=("Segoe UI", 20), relief="solid", bd=1, disabledforeground="#666", height=2).pack(fill="x", pady=(0, 34))

        controls = tk.Frame(root, bg="#f4f5f7")
        controls.pack(fill="x")
        for column, (target, name) in enumerate(DEVICES):
            controls.grid_columnconfigure(column, weight=1, uniform="device")
            cell = tk.Frame(controls, bg="#f4f5f7", padx=8)
            cell.grid(row=0, column=column, sticky="nsew")
            button = tk.Button(
                cell, text=f"Test {name}", command=lambda t=target: self.test_device(t),
                bg="#064887", fg="white", activebackground="#0b5aa4", activeforeground="white",
                font=("Segoe UI", 13, "bold"), relief="flat", cursor="hand2", height=2,
            )
            button.pack(fill="x")
            status = tk.Label(cell, text="●  Ready", font=("Segoe UI", 12), bg="#f4f5f7", fg="#15912a")
            status.pack(pady=12)
            self.buttons[target] = button
            self.statuses[target] = status

        title_row = tk.Frame(root, bg="#f4f5f7")
        title_row.pack(fill="x", pady=(18, 8))
        tk.Label(title_row, text="API Responses", font=("Segoe UI", 15, "bold"), bg="#f4f5f7", fg="#20242a").pack(side="left")
        tk.Button(title_row, text="Clear Log", command=self.clear_log, fg="#064887", font=("Segoe UI", 11, "bold"), relief="solid", bd=1, padx=16).pack(side="right")

        self.log = scrolledtext.ScrolledText(root, height=14, font=("Consolas", 11), relief="solid", bd=1, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def write_log(self, target: str, message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {target} — {message}\n"
        self.log.configure(state="normal")
        self.log.insert("end", line)
        self.log.see("end")
        self.log.configure(state="disabled")

    def test_device(self, target: str) -> None:
        self.buttons[target].configure(state="disabled")
        self.statuses[target].configure(text="●  Testing", fg="#c47b00")
        self.write_log(target, "Request sent")
        threading.Thread(target=self._request, args=(target,), daemon=True).start()

    def _request(self, target: str) -> None:
        payload = build_command_payload(target)
        try:
            request = Request(API_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=12) as response:
                result = json.loads(response.read().decode())
            self.after(0, self._finish, target, result.get("status", "failed"), result.get("message", "Unknown response"))
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            self.after(0, self._finish, target, "failed", f"API error {exc.code}: {detail}")
        except (URLError, TimeoutError) as exc:
            self.after(0, self._finish, target, "failed", f"API unavailable: {exc}")
        except Exception as exc:
            self.after(0, self._finish, target, "failed", f"Request failed: {exc}")

    def _finish(self, target: str, status: str, message: str) -> None:
        colors = {"completed": "#15912a", "timed_out": "#b35a00", "failed": "#b42318"}
        labels = {"completed": "Successful", "timed_out": "Timed Out", "failed": "Failed"}
        self.statuses[target].configure(text=f"●  {labels.get(status, status.title())}", fg=colors.get(status, "#b42318"))
        self.buttons[target].configure(state="normal")
        self.write_log(target, message)


if __name__ == "__main__":
    FakeIPC().mainloop()
