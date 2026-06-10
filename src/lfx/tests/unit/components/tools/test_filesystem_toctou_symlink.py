"""Regression for the validate-then-open TOCTOU symlink race.

A concurrent process can create a symlink at the validated target
between the validation step and the open(), causing the write to follow
the symlink and land outside the sandbox.

We deterministically reproduce the race by patching ``os.open`` so that,
right before the real open runs, a malicious symlink is dropped at the
candidate path. With ``O_NOFOLLOW`` semantics in the write helper this
open must fail with ``ELOOP``; the file outside ``<BASE>`` must remain
untouched.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent


@pytest.fixture
def base_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path / "fs"))
    return tmp_path


@pytest.fixture
def component(base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> FileSystemToolComponent:  # noqa: ARG001
    # base_dir fixture is consumed for its env-setting side effect.
    c = FileSystemToolComponent(root_path="", read_only=False)
    monkeypatch.setattr(c, "_resolve_auto_login", lambda: True)  # shared mode for simplicity
    return c


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics differ on Windows")
def test_should_refuse_when_target_becomes_symlink_between_validation_and_open(
    component: FileSystemToolComponent, base_dir: Path
) -> None:
    """``open()`` must not follow a symlink dropped after validation.

    Validation passes (target does not exist); a concurrent process
    creates a symlink at the validated path; ``open()`` must NOT follow
    it.
    """
    leak_target = base_dir / "outside.txt"
    leak_target.write_text("original", encoding="utf-8")

    namespace_root = base_dir / "fs" / "shared"
    target_path = namespace_root / "leak.txt"

    real_os_open = os.open
    raced = {"done": False}

    def racing_os_open(path, flags, mode=0o777, *args, **kwargs):
        # Right before opening the validated target, drop a symlink at it
        # — exactly the TOCTOU window. Only race once so the eventual
        # error path's open (e.g. for logging) is not also racing.
        if not raced["done"] and isinstance(path, (str, os.PathLike)) and str(path) == str(target_path):
            raced["done"] = True
            namespace_root.mkdir(parents=True, exist_ok=True)
            target_path.symlink_to(leak_target)
        return real_os_open(path, flags, mode, *args, **kwargs)

    with patch("os.open", racing_os_open):
        result = json.loads(json.dumps(component._write_file("leak.txt", "stolen")))

    # The file OUTSIDE the namespace MUST remain untouched.
    assert leak_target.read_text(encoding="utf-8") == "original", (
        f"TOCTOU: the write followed a symlink created mid-call and clobbered a file outside <BASE>; result={result!r}"
    )
    # If the tool reports success, the result must be a regular file inside
    # the namespace — never a symlink.
    if "error" not in result:
        assert target_path.exists()
        assert not target_path.is_symlink()
    # Confirm the race actually fired (otherwise the test is trivially passing).
    assert raced["done"], "the racing fixture never triggered; the test is not actually exercising the bug"


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics differ on Windows")
def test_should_refuse_to_read_through_symlink_dropped_mid_call(
    component: FileSystemToolComponent, base_dir: Path
) -> None:
    """Reads must not follow a symlink dropped after validation.

    Same race as the write case: a symlink dropped at the validated read
    target must not be followed to a file outside ``<BASE>``.
    """
    secret_outside = base_dir / "outside_secret.txt"
    secret_outside.write_text("TOP SECRET", encoding="utf-8")

    namespace_root = base_dir / "fs" / "shared"
    namespace_root.mkdir(parents=True, exist_ok=True)
    target_path = namespace_root / "innocent.txt"
    target_path.write_text("decoy", encoding="utf-8")  # validation sees a regular file

    real_os_open = os.open
    raced = {"done": False}

    def racing_os_open(path, flags, mode=0o777, *args, **kwargs):
        if not raced["done"] and isinstance(path, (str, os.PathLike)) and str(path) == str(target_path):
            raced["done"] = True
            target_path.unlink()
            target_path.symlink_to(secret_outside)
        return real_os_open(path, flags, mode, *args, **kwargs)

    with patch("os.open", racing_os_open):
        result = component._read_file("innocent.txt")

    # Either the read is refused (preferred) or it returns the decoy
    # content; it MUST NOT return the secret outside <BASE>.
    if "error" not in result:
        assert "TOP SECRET" not in result.get("content", ""), (
            f"TOCTOU: the read followed a symlink to a file outside <BASE>; result={result!r}"
        )
    assert raced["done"], "the racing fixture never triggered"
