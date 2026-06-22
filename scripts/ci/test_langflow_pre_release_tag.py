"""Unit tests for langflow_pre_release_tag.py.

Run directly or with pytest:

    cd scripts/ci && uv run python test_langflow_pre_release_tag.py
    cd scripts/ci && uv run python -m pytest test_langflow_pre_release_tag.py -q
"""

import contextlib
import io
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import langflow_pre_release_tag as pr


def test_ignores_unrelated_newer_pre_release_line():
    assert pr.create_tag("1.10.1", ["1.11.0.dev15"]) == "1.10.1rc0"


def test_increments_same_base_rc_with_or_without_dot():
    releases = ["1.10.1rc0", "1.10.1.rc1", "1.11.0.dev15"]
    assert pr.create_tag("1.10.1", releases) == "1.10.1rc2"


def test_final_same_base_starts_at_rc1():
    assert pr.create_tag("1.10.1", ["1.10.1"]) == "1.10.1rc1"


def test_shared_rc_number_floor_applies_to_other_package_base():
    assert pr.create_tag("0.10.1", [], rc_number=1) == "0.10.1rc1"


def test_shared_rc_number_floor_does_not_regress_existing_higher_rc():
    assert pr.create_tag("1.10.1", ["1.10.1rc5"], rc_number=1) == "1.10.1rc6"


def test_cli_reads_released_versions_from_stdin():
    output = io.StringIO()
    with (
        mock.patch.object(sys, "argv", ["langflow_pre_release_tag.py", "1.10.1", "--print-rc-number", "-"]),
        mock.patch.object(sys, "stdin", io.StringIO("1.10.1rc0\n1.11.0.dev15\n")),
        contextlib.redirect_stdout(output),
    ):
        pr.main()
    assert output.getvalue().strip() == "1"


def test_unparseable_versions_are_skipped():
    assert pr.create_tag("1.10.1", ["not-a-version", "1.10.1rc0"]) == "1.10.1rc1"


def _main():
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {exc}")
            else:
                print(f"ok   {name}")
    if failures:
        msg = f"{failures} test(s) failed."
        raise SystemExit(msg)
    print("All langflow_pre_release_tag tests passed.")


if __name__ == "__main__":
    _main()
