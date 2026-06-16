#!/usr/bin/env python
"""Update the version in frontend package.json."""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
EXPECTED_ARGS = 2


def update_frontend_version(version: str) -> None:
    """Update the version in src/frontend/package.json.

    Args:
        version: Version string with or without 'v' prefix (e.g., 'v1.11.0.dev9' or '1.11.0.dev9')
    """
    # Strip 'v' prefix if present
    version = version.lstrip("v")

    package_json_path = BASE_DIR / "src" / "frontend" / "package.json"

    if not package_json_path.exists():
        msg = f"package.json not found at {package_json_path}"
        raise FileNotFoundError(msg)

    # Read package.json
    with package_json_path.open("r", encoding="utf-8") as f:
        package_data = json.load(f)

    # Update version
    old_version = package_data.get("version", "unknown")
    package_data["version"] = version

    # Write back with proper formatting (2 space indent, newline at end)
    with package_json_path.open("w", encoding="utf-8") as f:
        json.dump(package_data, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline

    print(f"Updated frontend version: {old_version} -> {version}")


def main() -> None:
    if len(sys.argv) != EXPECTED_ARGS:
        print("Usage: update_frontend_version.py <version>")
        print("Example: update_frontend_version.py v1.11.0.dev9")
        sys.exit(1)

    version = sys.argv[1]
    update_frontend_version(version)


if __name__ == "__main__":
    main()
