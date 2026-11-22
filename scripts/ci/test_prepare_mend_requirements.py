"""Regression coverage for the complete hashed Mend requirements handoff."""

from __future__ import annotations

import copy
import hashlib
import http.client
import io
import socket
import sys
import threading
import urllib.request
from pathlib import Path

import pytest
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepare_mend_requirements as mend
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
    prepared, wheels = prepare_requirements(requirements, lock, python_version="3.12", wheel_directory="cpu-wheels")
    expected = requirements.replace("--extra-index-url https://download.pytorch.org/whl/cpu\n", "")
    assert prepared == "--find-links cpu-wheels\n" + expected
    assert [wheel.filename for wheel in wheels] == [
        "torch-2.14.0+cpu-cp312-cp312-manylinux_2_28_x86_64.whl",
        "torchvision-0.29.0+cpu-cp312-cp312-manylinux_2_28_x86_64.whl",
    ]
    assert prepared.count("--hash=sha256:") == requirements.count("--hash=sha256:")


def test_accepts_exported_cpu_artifact_host_alias(requirements, lock):
    requirements = requirements.replace(
        "--extra-index-url https://download.pytorch.org", "--extra-index-url https://download-r2.pytorch.org"
    )
    prepared, _ = prepare_requirements(requirements, lock, python_version="3.12")
    assert "--extra-index-url" not in prepared


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
    with pytest.raises(ValueError, match=r"Expected one locked|CPU artifact|not covered"):
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


@pytest.fixture
def downloadable(requirements, lock):
    payloads = {}
    for package in lock["package"]:
        payload = package["name"].encode()
        wheel = package["wheels"][0]
        digest = hashlib.sha256(payload).hexdigest()
        requirements = requirements.replace(wheel["hash"], f"sha256:{digest}")
        wheel.update(hash=f"sha256:{digest}", size=len(payload))
        payloads[wheel["url"]] = payload
    prepared, wheels = prepare_requirements(requirements, lock, python_version="3.12")
    return prepared, wheels, payloads


def _opener(monkeypatch, payloads):
    calls = []

    class Opener:
        def open(self, url, *, timeout):
            assert timeout > 0
            calls.append(url)
            return io.BytesIO(payloads[url])

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: Opener())
    return calls


def test_publishes_only_two_complete_hash_verified_wheels(tmp_path, monkeypatch, downloadable):
    _, wheels, payloads = downloadable
    calls = _opener(monkeypatch, payloads)
    destination = tmp_path / "cpu-wheels"
    mend.download_wheels(wheels, destination)
    assert calls == [wheel.url for wheel in wheels]
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == {
        wheel.filename: payloads[wheel.url] for wheel in wheels
    }
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("failure", ["wrong_hash", "truncated", "oversized", "network"])
def test_never_publishes_partial_or_unverified_wheels(tmp_path, monkeypatch, downloadable, failure):
    _, wheels, payloads = downloadable
    second = wheels[1]
    if failure == "wrong_hash":
        payloads[second.url] = b"x" * second.size
    elif failure == "truncated":
        payloads[second.url] = payloads[second.url][:-1]
    elif failure == "oversized":
        payloads[second.url] += b"x"
    _opener(monkeypatch, payloads)
    if failure == "network":
        monkeypatch.setattr(
            urllib.request, "build_opener", lambda *_handlers: (_ for _ in ()).throw(OSError("network"))
        )
    with pytest.raises((ValueError, OSError)):
        mend.download_wheels(wheels, tmp_path / "cpu-wheels")
    assert list(tmp_path.iterdir()) == []


def test_refuses_existing_wheel_directory_before_download(tmp_path, monkeypatch, downloadable):
    _, wheels, payloads = downloadable
    destination = tmp_path / "cpu-wheels"
    destination.mkdir()
    (destination / "existing").write_text("keep")
    calls = _opener(monkeypatch, payloads)
    with pytest.raises(FileExistsError):
        mend.download_wheels(wheels, destination)
    assert (destination / "existing").read_text() == "keep"
    assert calls == []


@pytest.mark.parametrize("url", ["http://download.pytorch.org/whl/cpu/file.whl", "https://example.com/file.whl"])
def test_refuses_redirect_to_unapproved_artifact_source(url):
    request = urllib.request.Request("https://download.pytorch.org/whl/cpu/file.whl")
    with pytest.raises(ValueError, match="CPU artifact"):
        mend.CpuArtifactRedirectHandler().redirect_request(request, None, 302, "Found", {}, url)


@pytest.mark.parametrize("size", [0, -1, True, "5", mend.MAX_WHEEL_BYTES + 1])
def test_refuses_invalid_lock_sizes(requirements, lock, size):
    lock["package"][0]["wheels"][0]["size"] = size
    with pytest.raises(ValueError, match="size"):
        prepare_requirements(requirements, lock, python_version="3.12")


def test_bounds_downloads_without_optional_lock_size(tmp_path, monkeypatch, downloadable):
    _, wheels, payloads = downloadable
    from dataclasses import replace

    wheels = [replace(wheel, size=None) for wheel in wheels]
    monkeypatch.setattr(mend, "MAX_WHEEL_BYTES", 8)
    _opener(monkeypatch, payloads)
    with pytest.raises(ValueError, match="size or time limit"):
        mend.download_wheels(wheels, tmp_path / "cpu-wheels")
    assert list(tmp_path.iterdir()) == []


def test_bounds_download_duration(tmp_path, monkeypatch, downloadable):
    _, wheels, payloads = downloadable
    values = iter([0, mend.DOWNLOAD_DEADLINE_SECONDS + 1])
    monkeypatch.setattr(mend.time, "monotonic", lambda: next(values))
    _opener(monkeypatch, payloads)
    with pytest.raises(ValueError, match="size or time limit"):
        mend.download_wheels(wheels, tmp_path / "cpu-wheels")
    assert list(tmp_path.iterdir()) == []


def test_checks_deadline_before_waiting_for_a_trickling_response(tmp_path, monkeypatch, downloadable):
    _, wheels, _ = downloadable
    client, server = socket.socketpair()
    client.settimeout(5)
    server.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nt")
    response = http.client.HTTPResponse(client)
    response.begin()
    checked = threading.Event()
    values = iter([0, mend.DOWNLOAD_DEADLINE_SECONDS + 1])
    errors = []

    def monotonic():
        value = next(values)
        if value:
            checked.set()
        return value

    class Opener:
        def open(self, _url, *, timeout):
            assert timeout == mend.DOWNLOAD_TIMEOUT_SECONDS
            return response

    def download():
        try:
            mend.download_wheels(wheels, tmp_path / "cpu-wheels")
        except (ValueError, OSError) as exc:
            errors.append(exc)

    monkeypatch.setattr(mend.time, "monotonic", monotonic)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: Opener())
    worker = threading.Thread(target=download)
    worker.start()
    try:
        assert checked.wait(2), "The helper waited for the rest of the body before checking its deadline"
        worker.join(2)
        assert not worker.is_alive()
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
        assert "time limit" in str(errors[0])
        assert list(tmp_path.iterdir()) == []
    finally:
        server.sendall(b"orch")
        server.close()
        worker.join(5)
        client.close()


def test_cli_keeps_scan_input_unchanged_when_a_download_fails(tmp_path, monkeypatch, requirements, lock):
    requirements_path = tmp_path / "requirements-mend.txt"
    requirements_path.write_text(requirements)
    lock_path = tmp_path / "uv.lock"
    lock_path.write_text("# Test manifest is supplied by the parser fixture\n")
    monkeypatch.setattr(tomllib, "loads", lambda _text: lock)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: (_ for _ in ()).throw(OSError("network")))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_mend_requirements.py",
            "--requirements",
            str(requirements_path),
            "--lock",
            str(lock_path),
            "--python-version",
            "3.12",
            "--wheel-dir",
            str(tmp_path / "cpu-wheels"),
        ],
    )
    with pytest.raises(OSError, match="network"):
        mend.main()
    assert requirements_path.read_text() == requirements
    assert sorted(path.name for path in tmp_path.iterdir()) == ["requirements-mend.txt", "uv.lock"]
