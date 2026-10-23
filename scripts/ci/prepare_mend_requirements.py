# ruff: noqa: EM101, EM102, TRY003
"""Bind Mend's CPU-only PyTorch requirements to their already-locked wheels.

pip applies index options to every requirement. Publishing the PyTorch index in
the compiled scan input makes Mend retry its public 403 responses for unrelated
PyPI packages. Mend handles direct archive requirements separately from its pip
resolution and can overwrite them with transitive index versions. A local wheel
directory keeps the original CPU version pins and hashes in that resolution.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import tomllib

CPU_INDEXES = frozenset({"https://download.pytorch.org/whl/cpu", "https://download-r2.pytorch.org/whl/cpu"})
CPU_PACKAGES = frozenset({"torch", "torchvision"})
PYPI_INDEX = "https://pypi.org/simple"
MAX_WHEEL_BYTES = 512 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_DEADLINE_SECONDS = 600


@dataclass(frozen=True)
class LockedWheel:
    url: str
    filename: str
    digest: str
    size: int | None


def validate_artifact_url(value: str) -> None:
    url = urlsplit(value)
    if (
        f"{url.scheme}://{url.netloc}/whl/cpu" not in CPU_INDEXES
        or not url.path.startswith("/whl/cpu/")
        or url.query
        or url.fragment
    ):
        raise ValueError("Expected an approved HTTPS CPU artifact URL")


class CpuArtifactRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_artifact_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def prepare_requirements(
    requirements: str, lock: dict, *, python_version: str, wheel_directory: str = ".mend-cpu-wheels"
) -> tuple[str, list[LockedWheel]]:
    """Preserve every compiled pin and hash, binding CPU wheels through find-links.

    The Mend job targets CPython on Linux x86_64. The locked PyTorch CPU wheels
    use manylinux_2_28, supported by its Ubuntu runner. Fail if this contract or
    either package's locked version, source, artifact, or accepted hash changes.
    """
    if not re.fullmatch(r"3\.\d+", python_version):
        raise ValueError("Expected a Python 3 major.minor version")
    if re.search(r"\s", wheel_directory) or not wheel_directory or wheel_directory.startswith("-"):
        raise ValueError("Expected a wheel directory without whitespace or option prefixes")
    python_tag = f"cp{python_version.replace('.', '')}"
    lines = iter(requirements.splitlines(keepends=True))
    output: list[str] = []
    replaced: set[str] = set()
    artifacts: list[LockedWheel] = []
    for first in lines:
        block = first
        last = first
        while last.rstrip().endswith("\\"):
            last = next(lines, "")
            if not last:
                raise ValueError("Unterminated requirement continuation")
            block += last
        if first.startswith(("--index-url ", "--extra-index-url ")):
            index = first.split(maxsplit=1)[1].strip().rstrip("/")
            if index in CPU_INDEXES:
                continue
            if index != PYPI_INDEX:
                raise ValueError("Unexpected package index in Mend requirements")
        match = re.fullmatch(r"(torch|torchvision)==([^\s;]+) \\\r?\n", first)
        if match is None:
            output.append(block)
            continue
        name, version = match.groups()
        if name in replaced:
            raise ValueError(f"Duplicate compiled requirement for {name}")
        packages = [
            package
            for package in lock["package"]
            if package["name"] == name
            and package["version"] == version
            and package.get("source", {}).get("registry") in CPU_INDEXES
        ]
        if len(packages) != 1 or not version.endswith("+cpu"):
            raise ValueError(f"Expected one locked CPU package for {name}=={version}")
        filename = f"{name}-{version}-{python_tag}-{python_tag}-manylinux_2_28_x86_64.whl"
        wheels = [
            wheel
            for wheel in packages[0].get("wheels", [])
            if unquote(urlsplit(wheel["url"]).path.rsplit("/", 1)[-1]) == filename
        ]
        if len(wheels) != 1:
            raise ValueError(f"Expected one locked Linux wheel for {name} on {python_version}")
        wheel = wheels[0]
        validate_artifact_url(wheel["url"])
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", wheel["hash"]) or f"--hash={wheel['hash']}" not in block.split():
            raise ValueError(f"Locked {name} wheel is not covered by the compiled CPU hashes")
        size = wheel.get("size")
        if size is not None and (type(size) is not int or not 0 < size <= MAX_WHEEL_BYTES):
            raise ValueError(f"Invalid locked CPU artifact size for {name}")
        artifacts.append(LockedWheel(wheel["url"], filename, wheel["hash"].removeprefix("sha256:"), size))
        output.append(block)
        replaced.add(name)
    if replaced != CPU_PACKAGES:
        raise ValueError("Mend requirements must include both pinned CPU torch and torchvision")
    return f"--find-links {wheel_directory}\n" + "".join(output), artifacts


def download_wheels(wheels: list[LockedWheel], destination: Path) -> None:
    """Publish the complete wheel directory only after validating both downloads."""
    if destination.exists():
        raise FileExistsError(f"CPU wheel directory already exists: {destination}")
    opener = urllib.request.build_opener(CpuArtifactRedirectHandler())
    with tempfile.TemporaryDirectory(prefix=".mend-cpu-wheels-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        for wheel in wheels:
            validate_artifact_url(wheel.url)
            digest = hashlib.sha256()
            size = 0
            deadline = time.monotonic() + DOWNLOAD_DEADLINE_SECONDS
            with (
                opener.open(wheel.url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response,
                (staging / wheel.filename).open("xb") as output,
            ):
                while chunk := response.read1(1024 * 1024):
                    size += len(chunk)
                    if (
                        size > (wheel.size if wheel.size is not None else MAX_WHEEL_BYTES)
                        or time.monotonic() > deadline
                    ):
                        raise ValueError(f"CPU artifact download exceeded its size or time limit: {wheel.filename}")
                    digest.update(chunk)
                    output.write(chunk)
            if (wheel.size is not None and size != wheel.size) or digest.hexdigest() != wheel.digest:
                raise ValueError(f"CPU artifact does not match its locked size and SHA256: {wheel.filename}")
        staging.rename(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    parser.add_argument("--requirements", type=Path, default=Path("requirements-mend.txt"))
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--wheel-dir", type=Path, help="Wheel directory inside the requirements file's scan directory")
    args = parser.parse_args()
    root = args.requirements.resolve().parent
    wheel_directory = (args.wheel_dir or root / ".mend-cpu-wheels").resolve()
    relative_wheel_directory = wheel_directory.relative_to(root).as_posix()
    prepared, wheels = prepare_requirements(
        args.requirements.read_text(encoding="utf-8"),
        tomllib.loads(args.lock.read_text(encoding="utf-8")),
        python_version=args.python_version,
        wheel_directory=relative_wheel_directory,
    )
    download_wheels(wheels, wheel_directory)
    args.requirements.write_text(prepared, encoding="utf-8")


if __name__ == "__main__":
    main()
