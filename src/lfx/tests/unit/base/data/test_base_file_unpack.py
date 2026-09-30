"""Security regression tests for BaseFileComponent bundle extraction.

Covers GHSA-ccv6-r384-xp75: a TAR member that is a symlink, hardlink, or device
node could be made to point at an arbitrary host file. When the extracted entry
is later read by `process_files()` the host file's contents would be ingested
into the downstream sink. The fix in `_safe_extract_tar` rejects every member
that is not a regular file or directory, and `_unpack_and_collect_files` skips
any symlinks defensively before handing entries to `process_files()`.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from typing import TYPE_CHECKING

import pytest
from lfx.base.data.base_file import BaseFileComponent

if TYPE_CHECKING:
    from pathlib import Path


class _StubFileComponent(BaseFileComponent):
    """Minimal concrete subclass used to exercise the unpack helpers."""

    VALID_EXTENSIONS = ["txt"]

    def __init__(self, **data):
        super().__init__(**data)
        self.set_attributes(
            {
                "path": [],
                "file_path": None,
                "separator": "\n\n",
                "silent_errors": False,
                "delete_server_file_after_processing": True,
                "ignore_unsupported_extensions": True,
                "ignore_unspecified_files": False,
            }
        )

    def process_files(self, file_list):  # pragma: no cover - not exercised here
        return file_list


def _add_file(tar: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.type = tarfile.REGTYPE
    tar.addfile(info, io.BytesIO(payload))


def _add_symlink(tar: tarfile.TarFile, name: str, target: str) -> None:
    info = tarfile.TarInfo(name=name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    tar.addfile(info)


def _add_hardlink(tar: tarfile.TarFile, name: str, target: str) -> None:
    info = tarfile.TarInfo(name=name)
    info.type = tarfile.LNKTYPE
    info.linkname = target
    tar.addfile(info)


def _add_fifo(tar: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name=name)
    info.type = tarfile.FIFOTYPE
    tar.addfile(info)


def _build_tar(tmp_path: Path, name: str, populate) -> Path:
    bundle = tmp_path / name
    with tarfile.open(bundle, "w") as tar:
        populate(tar)
    return bundle


def _build_zip(tmp_path: Path, name: str, files: dict[str, bytes]) -> Path:
    bundle = tmp_path / name
    with zipfile.ZipFile(bundle, "w") as zf:
        for member, payload in files.items():
            zf.writestr(member, payload)
    return bundle


@pytest.fixture
def component() -> _StubFileComponent:
    return _StubFileComponent()


def test_tar_with_absolute_symlink_is_rejected(tmp_path, component):
    """A symlink whose target is an absolute host path must be refused."""
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"jwt-signing-secret")

    bundle = _build_tar(
        tmp_path,
        "evil.tar",
        lambda tar: _add_symlink(tar, "leak", str(secret)),
    )

    extract_dir = tmp_path / "out_abs"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Refusing to extract link member"):
        component._unpack_bundle(bundle, extract_dir)
    assert list(extract_dir.iterdir()) == []


def test_tar_with_relative_escape_symlink_is_rejected(tmp_path, component):
    """A symlink that uses ../ to escape the extract dir must be refused."""
    bundle = _build_tar(
        tmp_path,
        "escape.tar",
        lambda tar: _add_symlink(tar, "leak", "../../etc/passwd"),
    )

    extract_dir = tmp_path / "out_rel"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Refusing to extract link member"):
        component._unpack_bundle(bundle, extract_dir)
    assert list(extract_dir.iterdir()) == []


def test_tar_with_hardlink_is_rejected(tmp_path, component):
    """Hardlinks have the same arbitrary-target risk as symlinks."""

    def populate(tar):
        _add_file(tar, "real.txt", b"ok")
        _add_hardlink(tar, "leak", "../etc/passwd")

    bundle = _build_tar(tmp_path, "hardlink.tar", populate)

    extract_dir = tmp_path / "out_hl"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Refusing to extract link member"):
        component._unpack_bundle(bundle, extract_dir)


def test_tar_with_fifo_member_is_rejected(tmp_path, component):
    """Non-regular members (FIFO/device) must be refused."""
    bundle = _build_tar(tmp_path, "fifo.tar", lambda tar: _add_fifo(tar, "pipe"))

    extract_dir = tmp_path / "out_fifo"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Refusing to extract non-regular TAR member"):
        component._unpack_bundle(bundle, extract_dir)


def test_tar_with_only_regular_files_extracts(tmp_path, component):
    """The fix must not regress benign archives."""

    def populate(tar):
        _add_file(tar, "a.txt", b"alpha")
        _add_file(tar, "nested/b.txt", b"beta")

    bundle = _build_tar(tmp_path, "ok.tar", populate)

    extract_dir = tmp_path / "out_ok"
    extract_dir.mkdir()
    component._unpack_bundle(bundle, extract_dir)

    assert (extract_dir / "a.txt").read_bytes() == b"alpha"
    assert (extract_dir / "nested" / "b.txt").read_bytes() == b"beta"


def test_zip_with_only_regular_files_extracts(tmp_path, component):
    """ZIP path must remain working unchanged."""
    bundle = _build_zip(tmp_path, "ok.zip", {"a.txt": b"alpha", "nested/b.txt": b"beta"})

    extract_dir = tmp_path / "out_zip"
    extract_dir.mkdir()
    component._unpack_bundle(bundle, extract_dir)

    assert (extract_dir / "a.txt").read_bytes() == b"alpha"
    assert (extract_dir / "nested" / "b.txt").read_bytes() == b"beta"


def test_collect_files_skips_symlinks_in_extracted_dir(tmp_path, component):
    """Defense-in-depth check for the post-extraction iteration.

    A symlink that somehow lands in an unpacked dir must not be passed to
    ``process_files()``. Simulated by manually planting one, since
    ``_safe_extract_tar`` would otherwise refuse it.
    """
    extract_root = tmp_path / "extracted"
    extract_root.mkdir()
    real = extract_root / "doc.txt"
    real.write_bytes(b"hello")
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"top-secret")
    (extract_root / "leak").symlink_to(secret)

    files = [BaseFileComponent.BaseFile(data=None, path=extract_root)]
    collected = component._unpack_and_collect_files(files)

    paths = {bf.path.name for bf in collected}
    assert "doc.txt" in paths
    assert "leak" not in paths


def test_unpack_bundle_rejects_unsupported_format(tmp_path, component):
    """An input that is neither zip nor tar still raises clearly."""
    bogus = tmp_path / "not-a-bundle.bin"
    bogus.write_bytes(b"not an archive")

    extract_dir = tmp_path / "out_bogus"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Unsupported bundle format"):
        component._unpack_bundle(bogus, extract_dir)


def test_real_filesystem_symlink_in_a_tar_via_tarfile_is_rejected(tmp_path, component):
    """End-to-end repro of the advisory's PoC archive shape.

    Builds the tar from a real filesystem symlink (the way the reporter's
    archive was produced) and confirms extraction is refused.
    """
    target = tmp_path / "host_secret"
    target.write_bytes(b"x")
    workdir = tmp_path / "src"
    workdir.mkdir()
    (workdir / "leak").symlink_to(target)

    bundle = tmp_path / "from_fs.tar"
    with tarfile.open(bundle, "w") as tar:
        tar.add(workdir / "leak", arcname="leak")

    extract_dir = tmp_path / "out_fs"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Refusing to extract link member"):
        component._unpack_bundle(bundle, extract_dir)
    assert list(extract_dir.iterdir()) == []
