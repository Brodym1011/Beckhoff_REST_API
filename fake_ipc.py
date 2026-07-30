"""Cross-platform PySide6 desktop IPC for RESTful multi-device actions."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


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
        "actions": {"Dispense": "dispense", "Drop Tip": "drop_tip", "Force Fail": "force_fail"},
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
            "Force Fail": "force_fail",
        },
    },
    "PLC": {
        "api_value": "plc",
        "devices": {"PLC": "plc"},
        "actions": {"Open Door": "open_door", "Close Door": "close_door", "Force Fail": "force_fail"},
    },
}


# Build the RESTful URL for a selected device type, name, and action.
def build_action_url(
    api_base_url: str,
    device_type: str,
    device_name: str,
    action: str,
) -> str:
    segments = (device_type, device_name, action)
    encoded = "/".join(quote(segment, safe="") for segment in segments)
    return f"{api_base_url.rstrip('/')}/{encoded}"


# Build the system-health URL from the user-selected API base URL.
def build_health_url(api_base_url: str) -> str:
    return f"{api_base_url.rstrip('/')}/system"


# Query the API heartbeat and convert failures into customer-readable text.
def check_api_health(api_base_url: str, opener=urlopen) -> tuple[bool, str]:
    try:
        with opener(build_health_url(api_base_url), timeout=3) as response:
            result = json.loads(response.read().decode())
        if result.get("heartbeat") is True:
            return True, "API Connected"
        return False, "Unable to connect to the API: unhealthy response"
    except Exception:
        return False, "Unable to connect to the API. Make sure the API is running."


# Submit one action and return the decoded API response.
def submit_action(
    api_base_url: str,
    device_type: str,
    device_name: str,
    action: str,
    opener=urlopen,
) -> dict:
    url = build_action_url(api_base_url, device_type, device_name, action)
    request = Request(url, data=b"", method="POST")
    with opener(request, timeout=12) as response:
        return json.loads(response.read().decode())


# Format the important API response fields for display in the GUI log.
def format_action_response(result: dict) -> str:
    return (
        f"device_type={result.get('device_type', 'unknown')} | "
        f"device_name={result.get('device_name', 'unknown')} | "
        f"action={result.get('action', 'unknown')} | "
        f"status={result.get('status', 'unknown')} | "
        f"message={result.get('message', 'Unknown response')}"
    )


class WorkerSignals(QObject):
    """Signals emitted by a background API worker."""

    finished = Signal(object)
    failed = Signal(str)


class ApiWorker(QRunnable):
    """Run a callable in Qt's thread pool and emit its result safely."""

    # Store the callable and arguments that will execute off the GUI thread.
    def __init__(self, function, *args) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.signals = WorkerSignals()

    # Execute the callable and convert exceptions into a Qt failure signal.
    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.function(*self.args))
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            self.signals.failed.emit(f"API error {exc.code}: {detail}")
        except (URLError, TimeoutError) as exc:
            self.signals.failed.emit(f"API unavailable: {exc}")
        except Exception as exc:
            self.signals.failed.emit(f"Request failed: {exc}")


class FakeIPC(QMainWindow):
    """Main PySide6 thick-client window."""

    # Initialize window state, widgets, thread pool, and health monitoring.
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Multi-Device Demo")
        self.resize(1280, 760)
        self.setMinimumSize(1000, 640)
        self.thread_pool = QThreadPool.globalInstance()
        self.health_check_running = False
        self._build()
        self._refresh_options()

        self.health_timer = QTimer(self)
        self.health_timer.setInterval(API_HEALTH_CHECK_INTERVAL_MS)
        self.health_timer.timeout.connect(self.check_connection)
        self.health_timer.start()
        QTimer.singleShot(0, self.check_connection)

    # Construct all visible widgets and the cross-platform dashboard layout.
    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(48, 28, 48, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(20)
        logo = QLabel()
        logo.setMinimumWidth(280)
        if BRANDING_PATH.exists():
            pixmap = QPixmap(str(BRANDING_PATH))
            logo.setPixmap(
                pixmap.scaled(
                    270,
                    82,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        header.addWidget(logo, 1)

        title = QLabel("Multi-Device Demo")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title, 1)

        connection = QVBoxLayout()
        connection.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.api_status_label = QLabel("●  API Checking")
        self.api_status_label.setObjectName("apiUnavailable")
        self.api_status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.api_tip_label = QLabel("Unable to connect to the API. Checking connection...")
        self.api_tip_label.setObjectName("apiTip")
        self.api_tip_label.setWordWrap(True)
        self.api_tip_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.api_tip_label.setMaximumWidth(290)
        connection.addWidget(self.api_status_label)
        connection.addWidget(self.api_tip_label)
        header.addLayout(connection, 1)
        root.addLayout(header)

        run_demo = QPushButton("Run Demo")
        run_demo.setObjectName("runDemo")
        run_demo.setEnabled(False)
        run_demo.setMaximumHeight(44)
        root.addWidget(run_demo)

        panel = QFrame()
        panel.setObjectName("actionPanel")
        panel_layout = QGridLayout(panel)
        panel_layout.setContentsMargins(28, 22, 28, 18)
        panel_layout.setHorizontalSpacing(18)
        panel_layout.setVerticalSpacing(14)

        self.type_combo = self._selector(panel_layout, 0, "Device Type", tuple(DEVICE_OPTIONS))
        self.name_combo = self._selector(panel_layout, 1, "Device Name", ())
        self.action_combo = self._selector(panel_layout, 2, "Action", ())
        self.type_combo.currentTextChanged.connect(self._refresh_options)

        self.execute_button = QPushButton("Execute Action")
        self.execute_button.setObjectName("executeButton")
        self.execute_button.setMinimumHeight(48)
        self.execute_button.clicked.connect(self.execute_action)
        panel_layout.addWidget(self.execute_button, 2, 0, 1, 3)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("successStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(self.status_label, 3, 0, 1, 3)
        root.addWidget(panel)

        log_header = QHBoxLayout()
        log_title = QLabel("API Responses")
        log_title.setObjectName("sectionTitle")
        log_header.addWidget(log_title)
        log_header.addStretch()
        clear_button = QPushButton("Clear Log")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(self.clear_log)
        log_header.addWidget(clear_button)
        root.addLayout(log_header)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Courier New", 10))
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.log, 1)

        endpoint = QHBoxLayout()
        endpoint.addWidget(QLabel("API Endpoint Base URL"))
        self.api_url_entry = QLineEdit(DEFAULT_API_BASE_URL)
        self.api_url_entry.setFont(QFont("Courier New", 10))
        self.api_url_entry.returnPressed.connect(self.check_connection)
        endpoint.addWidget(self.api_url_entry, 1)
        check_button = QPushButton("Check Connection")
        check_button.setObjectName("secondaryButton")
        check_button.clicked.connect(self.check_connection)
        endpoint.addWidget(check_button)
        root.addLayout(endpoint)

        self.setStyleSheet(
            """
            QWidget#central { background: #f4f5f7; color: #20242a; }
            QLabel { color: #20242a; }
            QLabel#title { font-size: 28px; font-weight: 700; }
            QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
            QLabel#apiUnavailable { color: #b42318; font-weight: 700; }
            QLabel#apiConnected { color: #15912a; font-weight: 700; }
            QLabel#apiTip { color: #7a271a; font-size: 12px; }
            QLabel#successStatus { color: #15912a; font-weight: 700; }
            QLabel#workingStatus { color: #c47b00; font-weight: 700; }
            QLabel#failedStatus { color: #b42318; font-weight: 700; }
            QFrame#actionPanel { background: white; border: 1px solid #c7cbd1; }
            QPushButton#runDemo { font-size: 15px; font-weight: 700; }
            QPushButton#executeButton {
                background: #064887; color: white; border: 0;
                font-size: 15px; font-weight: 700; padding: 10px;
            }
            QPushButton#executeButton:hover { background: #0b5aa4; }
            QPushButton#executeButton:disabled { background: #8a9aaa; }
            QPushButton#secondaryButton {
                color: #064887; background: white; border: 1px solid #064887;
                padding: 7px 12px; font-weight: 600;
            }
            QComboBox, QLineEdit, QPlainTextEdit {
                background: white;
                color: #20242a;
                border: 1px solid #9da3aa;
                padding: 7px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #20242a;
                selection-background-color: #dbe9f8;
                selection-color: #20242a;
                border: 1px solid #9da3aa;
            }
            """
        )

    # Create one labeled dropdown and add it to the action grid.
    def _selector(self, layout: QGridLayout, column: int, label: str, values) -> QComboBox:
        container = QVBoxLayout()
        heading = QLabel(label)
        heading.setStyleSheet("font-weight: 700; border: 0;")
        combo = QComboBox()
        combo.addItems(values)
        container.addWidget(heading)
        container.addWidget(combo)
        layout.addLayout(container, 0, column)
        return combo

    # Refresh device names and actions when the selected device type changes.
    @Slot()
    def _refresh_options(self) -> None:
        options = DEVICE_OPTIONS[self.type_combo.currentText()]
        self.name_combo.clear()
        self.name_combo.addItems(options["devices"])
        self.action_combo.clear()
        self.action_combo.addItems(options["actions"])

    # Start a non-blocking health check using the URL shown in the GUI.
    @Slot()
    def check_connection(self) -> None:
        api_base_url = self.api_url_entry.text().strip()
        if not api_base_url:
            self._set_api_status(False, "Unable to connect to the API. Enter an API URL.")
            return
        if self.health_check_running:
            return
        self.health_check_running = True
        worker = ApiWorker(check_api_health, api_base_url)
        worker.signals.finished.connect(self._health_check_finished)
        worker.signals.failed.connect(self._health_check_failed)
        self.thread_pool.start(worker)

    # Apply a completed health-check result to the connection indicator.
    @Slot(object)
    def _health_check_finished(self, result) -> None:
        self.health_check_running = False
        available, message = result
        self._set_api_status(available, message)

    # Display worker failures as an unavailable API state.
    @Slot(str)
    def _health_check_failed(self, message: str) -> None:
        self.health_check_running = False
        self._set_api_status(False, message)

    # Update the green or red API indicator and its connection tip.
    def _set_api_status(self, available: bool, message: str) -> None:
        if available:
            self.api_status_label.setText("●  API Connected")
            self.api_status_label.setObjectName("apiConnected")
            self.api_tip_label.clear()
        else:
            self.api_status_label.setText("●  API Unavailable")
            self.api_status_label.setObjectName("apiUnavailable")
            self.api_tip_label.setText(message)
        self.api_status_label.style().unpolish(self.api_status_label)
        self.api_status_label.style().polish(self.api_status_label)

    # Remove every entry from the response log.
    @Slot()
    def clear_log(self) -> None:
        self.log.clear()

    # Append a timestamped route and message to the response log.
    def write_log(self, route: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{timestamp}] {route} - {message}")

    # Resolve the selections and submit the action through Qt's thread pool.
    @Slot()
    def execute_action(self) -> None:
        options = DEVICE_OPTIONS[self.type_combo.currentText()]
        device_type = options["api_value"]
        device_name = options["devices"][self.name_combo.currentText()]
        action = options["actions"][self.action_combo.currentText()]
        api_base_url = self.api_url_entry.text().strip()
        route = f"{device_type}/{device_name}/{action}"

        if not api_base_url:
            self._set_api_status(False, "Unable to connect to the API. Enter an API URL.")
            return

        self.execute_button.setEnabled(False)
        self.status_label.setText("In Progress")
        self.status_label.setObjectName("workingStatus")
        self._refresh_status_style()
        self.write_log(route, "Request sent")

        worker = ApiWorker(
            submit_action,
            api_base_url,
            device_type,
            device_name,
            action,
        )
        worker.signals.finished.connect(self._action_finished)
        worker.signals.failed.connect(
            lambda message, selected_route=route: self._action_failed(selected_route, message)
        )
        self.thread_pool.start(worker)

    # Display a successful API response and restore the Execute button.
    @Slot(object)
    def _action_finished(self, result: dict) -> None:
        route = "/".join(
            (
                result.get("device_type", "unknown"),
                result.get("device_name", "unknown"),
                result.get("action", "unknown"),
            )
        )
        self._finish(route, result.get("status", "failed"), format_action_response(result))

    # Display a failed API request and restore the Execute button.
    def _action_failed(self, route: str, message: str) -> None:
        self._finish(route, "failed", message)

    # Present the terminal status and append it to the response log.
    def _finish(self, route: str, status: str, message: str) -> None:
        labels = {
            "completed": ("Successful", "successStatus"),
            "timed_out": ("Timed Out", "workingStatus"),
            "failed": ("Failed", "failedStatus"),
        }
        label, object_name = labels.get(status, (status.title(), "failedStatus"))
        self.status_label.setText(label)
        self.status_label.setObjectName(object_name)
        self._refresh_status_style()
        self.execute_button.setEnabled(True)
        self.write_log(route, message)

    # Reapply Qt style rules after changing a status label's object name.
    def _refresh_status_style(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


# Create the Qt application and run the desktop event loop.
def main() -> int:
    application = QApplication(sys.argv)
    window = FakeIPC()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
