"""Regression coverage for the complete hashed Mend requirements handoff."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_mend_requirements import prepare_requirements

TORCH_HASH = "a" * 64
VISION_HASH = "b" * 64
OTHER_HASH = "c" * 64


def _wheel(name: str, version: str, digest: str) -> dict[str, str]:
    return {
        "url": f"https://download-r2.pytorch.org/whl/cpu/{name}-{version}%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl",
        "hash": f"sha256:{digest}",
    }


@pytest.fixture
def lock() -> dict:
    return {
        "package": [
            {
                "name": name,
                "version": f"{version}+cpu",
                "source": {"registry": "https://download.pytorch.org/whl/cpu"},
                "wheels": [_wheel(name, version, digest)],
            }
            for name, version, digest in [("torch", "2.14.0", TORCH_HASH), ("torchvision", "0.29.0", VISION_HASH)]
        ]
    }


@pytest.fixture
def requirements() -> str:
    return (
        "--index-url https://pypi.org/simple\n"
        "--extra-index-url https://download.pytorch.org/whl/cpu\n\n"
        f"a2a-sdk==1.2.1 \\\n    --hash=sha256:{OTHER_HASH}\n"
        f"torch==2.14.0+cpu \\\n    --hash=sha256:{TORCH_HASH} \\\n    --hash=sha256:{OTHER_HASH}\n"
        f"torchvision==0.29.0+cpu \\\n    --hash=sha256:{VISION_HASH}\n"
        f"zipp==3.23.0 \\\n    --hash=sha256:{OTHER_HASH}\n"
    )


def test_preserves_every_requirement_and_hash_without_global_torch_index(requirements, lock):
    prepared = prepare_requirements(requirements, lock, python_version="3.12")
    expected = requirements.replace("--extra-index-url https://download.pytorch.org/whl/cpu\n", "")
    for package in lock["package"]:
        expected = expected.replace(
            f"{package['name']}=={package['version']}", f"{package['name']} @ {package['wheels'][0]['url']}"
        )
    assert prepared == expected
    assert prepared.count("--hash=sha256:") == requirements.count("--hash=sha256:")


def test_accepts_exported_cpu_artifact_host_alias(requirements, lock):
    requirements = requirements.replace(
        "--extra-index-url https://download.pytorch.org", "--extra-index-url https://download-r2.pytorch.org"
    )
    assert "--extra-index-url" not in prepare_requirements(requirements, lock, python_version="3.12")


@pytest.mark.parametrize(
    "change", ["version", "registry", "missing_wheel", "wrong_python", "duplicate_wheel", "foreign_url", "hash"]
)
def test_refuses_changed_or_unverified_cpu_artifacts(requirements, lock, change):
    package = lock["package"][0]
    if change == "version":
        package["version"] = "2.15.0+cpu"
    elif change == "registry":
        package["source"]["registry"] = "https://pypi.org/simple"
    elif change == "missing_wheel":
        package["wheels"] = []
    elif change == "wrong_python":
        package["wheels"][0]["url"] = package["wheels"][0]["url"].replace("cp312", "cp313")
    elif change == "duplicate_wheel":
        package["wheels"].append(copy.deepcopy(package["wheels"][0]))
    elif change == "foreign_url":
        package["wheels"][0]["url"] = package["wheels"][0]["url"].replace("download-r2.pytorch.org", "example.com")
    else:
        package["wheels"][0]["hash"] = "sha256:" + "d" * 64
    with pytest.raises(ValueError, match=r"Expected one locked|not covered"):
        prepare_requirements(requirements, lock, python_version="3.12")


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.replace("torch==2.14.0+cpu", "torch==2.14.0"),
        lambda value: value.replace("torch==2.14.0+cpu", "torch>=2.14.0+cpu"),
        lambda value: value.replace("torchvision==0.29.0+cpu", "other==0.29.0"),
        lambda value: value + f"torch==2.14.0+cpu \\\n    --hash=sha256:{TORCH_HASH}\n",
        lambda value: value + "--extra-index-url https://example.com/simple\n",
        lambda value: value + "unfinished==1.0 \\\n",
    ],
)
def test_refuses_incomplete_or_ambiguous_scan_input(requirements, lock, change):
    with pytest.raises(
        ValueError, match=r"Expected one locked|must include both|Duplicate compiled|Unexpected package|Unterminated"
    ):
        prepare_requirements(change(requirements), lock, python_version="3.12")
