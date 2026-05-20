"""Regression for the ``.lfsig`` reservation case-sensitivity bypass.

The reservation is enforced via case-sensitive equality at
``_validate_path``. APFS and NTFS treat ``.LFSIG`` and ``.lfsig`` as the
same directory, so any uppercase / mixed-case variant bypasses the
reservation on those platforms.

The guard must reject every case variation regardless of host OS — flows
authored on Linux must not silently break the reservation on macOS or
Windows.
"""

from pathlib import Path

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent


@pytest.fixture
def component(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FileSystemToolComponent:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    c = FileSystemToolComponent(root_path="", read_only=False)
    # Shared mode keeps the test focused on the reservation guard, not on
    # user-isolation plumbing.
    monkeypatch.setattr(c, "_resolve_auto_login", lambda: True)
    return c


@pytest.mark.parametrize(
    "variant",
    [
        ".LFSIG",
        ".LfSiG",
        ".lfSIG",
        ".LFSIG/poison.json",
        "subdir/.LFSIG/x",
        "subdir/.LfSig",
    ],
)
def test_should_reject_uppercase_reserved_segment_variants(component: FileSystemToolComponent, variant: str) -> None:
    """write_file must refuse every case variant of the reserved segment."""
    leaf = variant if "/" in variant else f"{variant}/poison.json"
    result = component._write_file(leaf, "{}")

    assert "error" in result, f"variant {leaf!r} bypassed the .lfsig reservation; result={result!r}"
    assert "reserved" in result["error"].lower()


def test_lowercase_segment_remains_rejected(component: FileSystemToolComponent) -> None:
    """The original (lowercase) reservation must still hold after the fix."""
    result = component._write_file(".lfsig/x.json", "{}")
    assert "error" in result
    assert "reserved" in result["error"].lower()
