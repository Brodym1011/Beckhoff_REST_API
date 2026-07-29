"""Export the FastAPI OpenAPI schema to the project root."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from source.main import app  # noqa: E402


# Serialize FastAPI's live schema into the versioned project document.
def main() -> None:
    output_path = PROJECT_ROOT / "openapi.json"
    output_path.write_text(
        json.dumps(app.openapi(), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
