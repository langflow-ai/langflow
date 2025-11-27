#!/usr/bin/env python3
"""Check for deprecated langchain import patterns in component files.

This script scans all Python files in the lfx/components directory for
deprecated import patterns and reports them. It's designed to be used
as a pre-commit hook to catch import issues early.

Exit codes:
    0: No deprecated imports found
    1: Deprecated imports found
    2: Error during execution
"""

import ast
import sys
from pathlib import Path


def check_deprecated_imports(components_path: Path) -> list[str]:
    """Check for deprecated import patterns in component files.

    Args:
        components_path: Path to the components directory

    Returns:
        List of error messages for deprecated imports found
    """
    deprecated_imports = []

    # Known deprecated import patterns
    deprecated_patterns = [
        ("langchain.embeddings.base", "langchain_core.embeddings"),
        ("langchain.llms.base", "langchain_core.language_models.llms"),
        ("langchain.chat_models.base", "langchain_core.language_models.chat_models"),
        ("langchain.schema", "langchain_core.messages"),
        ("langchain.vectorstores", "langchain_community.vectorstores"),
        ("langchain.document_loaders", "langchain_community.document_loaders"),
        ("langchain.text_splitter", "langchain_text_splitters"),
    ]

    # Walk through all Python files in components
    for py_file in components_path.rglob("*.py"):
        # Skip private modules
        if py_file.name.startswith("_"):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""

                    # Check against deprecated patterns
                    for deprecated, replacement in deprecated_patterns:
                        if module.startswith(deprecated):
                            relative_path = py_file.relative_to(components_path.parent)
                            deprecated_imports.append(
                                f"{relative_path}:{node.lineno}: "
                                f"Uses deprecated '{deprecated}' - should use '{replacement}'"
                            )

        except Exception as e:  # noqa: BLE001
            # Report parsing errors but continue - we want to check all files
            print(f"Warning: Could not parse {py_file}: {e}", file=sys.stderr)
            continue

    return deprecated_imports


def main() -> int:
    """Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for deprecated imports found, 2 for error)
    """
    try:
        # Find the lfx components directory
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent
        lfx_components = repo_root / "src" / "lfx" / "src" / "lfx" / "components"

        if not lfx_components.exists():
            print(f"Error: Components directory not found at {lfx_components}", file=sys.stderr)
            return 2

        # Check for deprecated imports
        deprecated_imports = check_deprecated_imports(lfx_components)

        if deprecated_imports:
            print("❌ Found deprecated langchain imports:", file=sys.stderr)
            print(file=sys.stderr)
            for imp in deprecated_imports:
                print(f"  • {imp}", file=sys.stderr)
            print(file=sys.stderr)
            print(
                "Please update these imports to use the current langchain import paths.",
                file=sys.stderr,
            )
            print("See: https://python.langchain.com/docs/versions/migrating_chains/", file=sys.stderr)
            return 1
        # No deprecated imports found
        print("✅ No deprecated imports found")
    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors during script execution
        print(f"Error: {e}", file=sys.stderr)
        return 2
    else:
        # Success case - no exceptions and no deprecated imports
        return 0


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
