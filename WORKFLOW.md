# IPC and REST API Workflow

```mermaid
flowchart TD
    Start[Start PySide6 desktop IPC] --> Health[GET /api/v1/system]
    Health --> Available{API available?}
    Available -- Yes --> Green[Show green API Connected light]
    Available -- No --> Red[Show red API Unavailable light and connection tip]
    Green --> Repeat[Repeat health check every 5 seconds]
    Red --> Repeat
    Repeat --> Health

    User[User selects Device Type, Device Name, and Action] --> Execute[Click Execute Action]
    Execute --> Disable[Disable Execute button and show In Progress]
    Disable --> Build[Build POST /api/v1/device_type/device_name/action]
    Build --> Handler{Matching FastAPI route?}

    Handler -- No --> Invalid[Return HTTP 404 with standardized error]
    Invalid --> InvalidType[UNKNOWN_DEVICE_TYPE]
    Invalid --> InvalidName[UNKNOWN_DEVICE]
    Invalid --> InvalidAction[UNSUPPORTED_ACTION]

    Handler -- Yes --> ActionFunction[Call explicit device action function]
    ActionFunction --> Router[Command router validates type, name, and action]
    Router --> Registry[Device registry selects target adapter]
    Registry --> Adapter[Mock adapter executes configured outcome]

    Adapter --> Outcome{Configured result}
    Outcome -- Success --> Completed[status: completed]
    Outcome -- Failure --> Failed[status: failed]
    Outcome -- Unavailable --> Unavailable[DEVICE_UNAVAILABLE]
    Outcome -- Timeout --> Timeout[status: timed_out]

    Completed --> Response[Return standardized JSON response]
    Failed --> Response
    Unavailable --> Response
    Timeout --> Response

    Response --> Echo[Echo device_type, device_name, action, status, and message]
    Echo --> Display[Append result to IPC response log]
    Display --> Enable[Re-enable Execute button and show terminal status]
```

## Supported action paths

```text
POST /api/v1/flex/{device_name}/dispense
POST /api/v1/flex/{device_name}/drop_tip
POST /api/v1/arm/{device_name}/grab_sample
POST /api/v1/arm/{device_name}/drop_sample
POST /api/v1/plc/{device_name}/open_door
POST /api/v1/plc/{device_name}/close_door
```

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| PySide6 IPC | Collects selections, checks API availability, submits actions, and displays results. |
| FastAPI endpoint | Matches the explicit action route and returns HTTP validation errors. |
| Command router | Validates the type/name/action combination and requests the correct adapter. |
| Device registry | Maps Flex 1, Flex 2, PLC, Static Arm, and Tracked Arm to adapter instances. |
| Mock adapter | Simulates success, failure, unavailable, or timeout behavior without hardware. |
| Response model | Returns the device type, device name, action, status, message, request ID, and completion time. |

## Current boundary

The **Run Demo** button is visible but disabled. It does not call the API until
the ordered demo sequence and orchestration rules are defined.
