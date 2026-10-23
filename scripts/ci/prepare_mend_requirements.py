# ruff: noqa: EM101, EM102, TRY003
"""Bind Mend's CPU-only PyTorch requirements to their already-locked wheels.

pip applies index options to every requirement. Publishing the PyTorch index in
the compiled scan input makes Mend retry its public 403 responses for unrelated
PyPI packages. Direct wheel requirements preserve the resolved CPU versions and
hashes without making that index a source for every other dependency.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import tomllib

CPU_INDEXES = frozenset({"https://download.pytorch.org/whl/cpu", "https://download-r2.pytorch.org/whl/cpu"})
CPU_PACKAGES = frozenset({"torch", "torchvision"})
PYPI_INDEX = "https://pypi.org/simple"


def prepare_requirements(requirements: str, lock: dict, *, python_version: str) -> str:
    """Preserve the compiled inventory and hashes, replacing only CPU wheel pins.

    The Mend job targets CPython on Linux x86_64. The locked PyTorch CPU wheels
    use manylinux_2_28, supported by its Ubuntu runner. Fail if this contract or
    either package's locked version, source, artifact, or accepted hash changes.
    """
    if not re.fullmatch(r"3\.\d+", python_version):
        raise ValueError("Expected a Python 3 major.minor version")
    python_tag = f"cp{python_version.replace('.', '')}"
    lines = iter(requirements.splitlines(keepends=True))
    output: list[str] = []
    replaced: set[str] = set()
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
        url = urlsplit(wheel["url"])
        if (
            f"{url.scheme}://{url.netloc}/whl/cpu" not in CPU_INDEXES
            or not url.path.startswith("/whl/cpu/")
            or url.query
            or url.fragment
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", wheel["hash"])
            or f"--hash={wheel['hash']}" not in block.split()
        ):
            raise ValueError(f"Locked {name} wheel is not covered by the compiled CPU hashes")
        output.append(block.replace(first, f"{name} @ {wheel['url']} \\\n", 1))
        replaced.add(name)
    if replaced != CPU_PACKAGES:
        raise ValueError("Mend requirements must include both pinned CPU torch and torchvision")
    return "".join(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    parser.add_argument("--requirements", type=Path, default=Path("requirements-mend.txt"))
    parser.add_argument("--python-version", required=True)
    args = parser.parse_args()
    prepared = prepare_requirements(
        args.requirements.read_text(encoding="utf-8"),
        tomllib.loads(args.lock.read_text(encoding="utf-8")),
        python_version=args.python_version,
    )
    args.requirements.write_text(prepared, encoding="utf-8")


if __name__ == "__main__":
    main()
