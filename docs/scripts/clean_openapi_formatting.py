#!/usr/bin/env python3
"""Clean OpenAPI specification formatting for better ReDoc display.

This script converts newlines in descriptions to HTML breaks for proper
rendering in ReDoc documentation.
"""

import json
import sys
from pathlib import Path

MIN_ARGS = 2


def clean_openapi_formatting(input_file: str, output_file: str | None = None) -> None:
    """Clean OpenAPI spec formatting by converting newlines to HTML breaks.

    Args:
        input_file: Path to input OpenAPI JSON file
        output_file: Path to output file (defaults to overwriting input)
    """
    if output_file is None:
        output_file = input_file

    try:
        # Load the OpenAPI spec
        input_path = Path(input_file)
        with input_path.open(encoding="utf-8") as f:
            spec = json.load(f)

        # Fix description formatting by converting newlines to HTML breaks
        if "paths" in spec:
            for path_item in spec["paths"].values():
                for operation in path_item.values():
                    if isinstance(operation, dict) and "description" in operation:
                        description = operation["description"]
                        if description:
                            # Convert newlines to HTML breaks for better ReDoc rendering
                            operation["description"] = description.replace("\n", "<br>")

        # Save the cleaned spec
        output_path = Path(output_file)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

        # Success message (using sys.stdout for consistency)
        sys.stdout.write(f"OpenAPI spec cleaned successfully: {output_file}\n")

    except FileNotFoundError:
        sys.stderr.write(f"Error: File not found: {input_file}\n")
        sys.exit(1)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error: Invalid JSON in {input_file}: {e}\n")
        sys.exit(1)
    except OSError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < MIN_ARGS:
        sys.stderr.write("Usage: python clean_openapi_formatting.py <input_file> [output_file]\n")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > MIN_ARGS else None

    clean_openapi_formatting(input_file, output_file)


if __name__ == "__main__":
    main()
