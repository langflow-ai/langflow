#!/usr/bin/env python3
r"""Script to verify that all changed files in src/frontend are covered by patterns in changes-filter.yaml.

This ensures that CI workflows (especially Playwright tests) are triggered appropriately for frontend changes.

Usage:
    # Check files changed in current branch vs main
    git diff --name-only origin/main HEAD | python scripts/check_changes_filter.py

    # Check specific files
    echo -e "src/frontend/file1.tsx\nsrc/frontend/file2.ts" | python scripts/check_changes_filter.py

Note:
    Only files under src/frontend/ are checked. All other files are ignored.

Exit codes:
    0 - All frontend files are covered by patterns
    1 - Some frontend files are not covered (or error occurred)
"""

import fnmatch
import sys
from pathlib import Path

import yaml


def load_filter_patterns(filter_file: Path) -> dict[str, list[str]]:
    """Load all patterns from the changes-filter.yaml file."""
    with filter_file.open() as f:
        return yaml.safe_load(f)


def get_changed_files_from_stdin() -> list[str]:
    """Get list of changed files from stdin (one per line), filtered to src/frontend only."""
    files = []
    for line in sys.stdin:
        stripped = line.strip()
        if stripped and stripped.startswith("src/frontend/"):
            files.append(stripped)
    return files


def matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if a file matches a glob pattern.

    Handles both directory patterns (ending with /**) and file patterns.
    """
    # Remove leading ./ if present
    file_path = file_path.lstrip("./")
    pattern = pattern.lstrip("./")

    # Convert ** patterns to match any depth
    if "**" in pattern:
        # For patterns like "src/backend/**", match any file under that directory
        if pattern.endswith("/**"):
            base_dir = pattern[:-3]
            return file_path.startswith(base_dir)
        # For patterns like "src/backend/**.py", match files at any depth with that extension
        pattern = pattern.replace("**", "*")

    # Use fnmatch for glob pattern matching
    return fnmatch.fnmatch(file_path, pattern)


def check_file_coverage(changed_files: list[str], filter_patterns: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Check which files are covered by at least one pattern.

    Returns: (covered_files, uncovered_files)
    """
    # Flatten all patterns from all categories
    all_patterns = []
    for category_patterns in filter_patterns.values():
        all_patterns.extend(category_patterns)

    covered = []
    uncovered = []

    for file_path in changed_files:
        is_covered = False
        for pattern in all_patterns:
            if matches_pattern(file_path, pattern):
                is_covered = True
                break

        if is_covered:
            covered.append(file_path)
        else:
            uncovered.append(file_path)

    return covered, uncovered


def main():
    """Main execution function."""
    # Get repository root
    repo_root = Path(__file__).parent.parent
    filter_file = repo_root / ".github" / "changes-filter.yaml"

    if not filter_file.exists():
        print(f"Error: Filter file not found at {filter_file}")
        sys.exit(1)

    # Load filter patterns
    filter_patterns = load_filter_patterns(filter_file)

    # Get changed files from stdin
    changed_files = get_changed_files_from_stdin()

    if not changed_files:
        print("No changed files detected.")
        return

    print(f"Checking {len(changed_files)} changed file(s) against filter patterns...")
    print()

    # Check coverage
    covered, uncovered = check_file_coverage(changed_files, filter_patterns)

    # Report results
    if uncovered:
        print("❌ FAILURE: The following files are NOT covered by any pattern in changes-filter.yaml:")
        print()
        for file_path in sorted(uncovered):
            print(f"  - {file_path}")
        print()
        print(f"Total: {len(uncovered)} uncovered file(s) out of {len(changed_files)}")
        print()
        print("Please update .github/changes-filter.yaml to include patterns for these files.")
        sys.exit(1)
    else:
        print("✅ SUCCESS: All changed files are covered by patterns in changes-filter.yaml")
        print()
        print(f"Checked {len(changed_files)} file(s):")
        for file_path in sorted(covered):
            print(f"  ✓ {file_path}")


if __name__ == "__main__":
    main()
