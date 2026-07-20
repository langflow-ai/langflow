"""Tests for content-aware bundle release planning and publication."""

# ruff: noqa: S603

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bundle_release_plan import (
    PlanError,
    PublishResult,
    build_artifact_plan,
    build_change_plan,
    bump_version,
    publish_artifacts,
    read_wheel,
    restamp_unpublished_bundles,
    restamp_version,
    update_changed_bundles,
    wait_for_artifacts,
)


class FakeIndex:
    """Deterministic package-index fake with optional delayed responses."""

    def __init__(self) -> None:
        self.releases: dict[tuple[str, str], list[dict[str, Any] | None]] = defaultdict(list)
        self.downloads: dict[str, bytes] = {}
        self.calls: dict[tuple[str, str], int] = defaultdict(int)

    def queue(self, package: str, version: str, *responses: dict[str, Any] | None) -> None:
        self.releases[(package, version)].extend(responses)

    def get_release(self, package: str, version: str) -> dict[str, Any] | None:
        key = (package, version)
        self.calls[key] += 1
        responses = self.releases[key]
        if not responses:
            return None
        if len(responses) == 1:
            return responses[0]
        return responses.pop(0)

    def download(self, url: str) -> bytes:
        return self.downloads[url]


def _run(repo: Path, *args: str) -> None:
    subprocess.run(args, cwd=repo, check=True, capture_output=True)


def _bundle_pyproject(name: str, version: str) -> str:
    return f"""[project]
name = "{name}"
version = "{version}"
dependencies = ["lfx>=1.11.0.dev0,<2.0.0"]
"""


def _create_repository(tmp_path: Path, versions: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src" / "lfx").mkdir(parents=True)
    (repo / "src" / "lfx" / "pyproject.toml").write_text(
        '[project]\nname = "lfx"\nversion = "1.11.0"\n', encoding="utf-8"
    )
    dependencies: list[str] = []
    lock_packages: list[str] = []
    for directory, version in versions.items():
        name = f"lfx-{directory}"
        dependencies.append(f'    "{name}>={version},<1.0.0",')
        lock_packages.append(f'[[package]]\nname = "{name}"\nversion = "{version}"\n')
        package_dir = repo / "src" / "bundles" / directory
        source_dir = package_dir / "src" / name.replace("-", "_")
        source_dir.mkdir(parents=True)
        (package_dir / "pyproject.toml").write_text(_bundle_pyproject(name, version), encoding="utf-8")
        (package_dir / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        (source_dir / "component.py").write_text("VALUE = 1\n", encoding="utf-8")
        (source_dir / "extension.json").write_text(
            json.dumps({"id": name, "version": version}, indent=2) + "\n", encoding="utf-8"
        )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "langflow"\nversion = "1.11.0"\ndependencies = [\n' + "\n".join(dependencies) + "\n]\n",
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text("version = 1\n\n" + "\n".join(lock_packages), encoding="utf-8")
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "tests@example.com")
    _run(repo, "git", "config", "user.name", "Bundle Tests")
    _run(repo, "git", "config", "commit.gpgsign", "false")
    _run(repo, "git", "add", ".")
    _run(repo, "git", "commit", "-qm", "base")
    return repo


def _refresh_lock(repo: Path) -> None:
    packages: list[str] = []
    for pyproject in sorted((repo / "src" / "bundles").glob("*/pyproject.toml")):
        content = pyproject.read_text(encoding="utf-8")
        name = content.split('name = "', 1)[1].split('"', 1)[0]
        version = content.split('version = "', 1)[1].split('"', 1)[0]
        packages.append(f'[[package]]\nname = "{name}"\nversion = "{version}"\n')
    (repo / "uv.lock").write_text("version = 1\n\n" + "\n".join(packages), encoding="utf-8")


def _make_wheel(tmp_path: Path, package: str, version: str, payload: str) -> Path:
    normalized = package.replace("-", "_")
    wheel_path = tmp_path / f"{normalized}-{version}-py3-none-any.whl"
    dist_info = f"{normalized}-{version}.dist-info"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(f"{normalized}/component.py", payload)
        wheel.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.3\nName: {package}\nVersion: {version}\nRequires-Dist: lfx<2,>=1.11.0.dev0\n\n",
        )
        wheel.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\n")
        wheel.writestr(f"{dist_info}/RECORD", "")
    return wheel_path


def _matching_release(wheel: Path) -> dict[str, Any]:
    return {
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "url": f"https://files.example/{wheel.name}",
                "digests": {"sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()},
            }
        ]
    }


def test_noop_ignores_bundle_docs_and_tests(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    (repo / "src" / "bundles" / "alpha" / "README.md").write_text("docs only\n", encoding="utf-8")

    assert build_change_plan("HEAD", base_dir=repo) == ()


def test_single_bundle_source_change_requires_version_bump(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    source = repo / "src" / "bundles" / "alpha" / "src" / "lfx_alpha" / "component.py"
    source.write_text("VALUE = 2\n", encoding="utf-8")

    plan = build_change_plan("HEAD", base_dir=repo)

    assert len(plan) == 1
    assert plan[0].name == "lfx-alpha"
    assert plan[0].source_changed is True
    assert "version remains 0.1.0" in plan[0].errors[0]


def test_multi_bundle_update_changes_versions_ranges_manifests_and_lock(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0", "beta": "0.2.4"})
    for directory in ("alpha", "beta"):
        source = repo / "src" / "bundles" / directory / "src" / f"lfx_{directory}" / "component.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")

    plan = update_changed_bundles("HEAD", base_dir=repo, run_lock=lambda: _refresh_lock(repo))

    assert {(entry.name, entry.version) for entry in plan} == {("lfx-alpha", "0.1.1"), ("lfx-beta", "0.2.5")}
    assert all(not entry.errors for entry in plan)
    root = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert '"lfx-alpha>=0.1.1,<1.0.0"' in root
    assert '"lfx-beta>=0.2.5,<1.0.0"' in root
    assert 'version = "0.1.1"' in (repo / "src" / "bundles" / "alpha" / "pyproject.toml").read_text()
    alpha_manifest = json.loads(
        (repo / "src" / "bundles" / "alpha" / "src" / "lfx_alpha" / "extension.json").read_text()
    )
    assert alpha_manifest["version"] == "0.1.1"
    assert 'name = "lfx-beta"\nversion = "0.2.5"' in (repo / "uv.lock").read_text()


def test_prerelease_versions_share_the_requested_restamp() -> None:
    assert restamp_version("0.3.0", "rc4") == "0.3.0rc4"
    assert bump_version("0.2.9", prerelease="rc0") == "0.2.10rc0"
    assert bump_version("1.2.3", bump="minor", prerelease=".dev7") == "1.3.0.dev7"


def test_prerelease_restamp_reuses_stable_and_changes_only_unpublished_bundle(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1", "beta": "0.2.0"})
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1", {"urls": [{"packagetype": "bdist_wheel"}]})
    index.queue("lfx-beta", "0.2.0", None)

    plan = restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    assert [(entry.package, entry.build_version, entry.action) for entry in plan] == [
        ("lfx-alpha", "0.1.1", "reuse-stable"),
        ("lfx-beta", "0.2.0rc3", "publish-prerelease"),
    ]
    alpha = (repo / "src" / "bundles" / "alpha" / "pyproject.toml").read_text()
    beta = (repo / "src" / "bundles" / "beta" / "pyproject.toml").read_text()
    assert 'version = "0.1.1"' in alpha
    assert '"lfx>=1.11.0.dev0,<2.0.0"' in alpha
    assert 'version = "0.2.0rc3"' in beta
    assert '"lfx>=1.11.0rc3,<2.0.0"' in beta


def test_partial_publication_reuses_matching_and_plans_only_missing(tmp_path: Path) -> None:
    alpha = _make_wheel(tmp_path, "lfx-alpha", "0.1.1", "ALPHA = 1\n")
    beta = _make_wheel(tmp_path, "lfx-beta", "0.2.0", "BETA = 1\n")
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1", _matching_release(alpha))
    index.queue("lfx-beta", "0.2.0", None)

    plan = build_artifact_plan([beta, alpha], index)

    assert [(entry.package, entry.action) for entry in plan] == [
        ("lfx-alpha", "reuse"),
        ("lfx-beta", "publish"),
    ]


def test_partial_publish_only_uploads_missing_artifact(tmp_path: Path) -> None:
    alpha = _make_wheel(tmp_path, "lfx-alpha", "0.1.1", "ALPHA = 1\n")
    beta = _make_wheel(tmp_path, "lfx-beta", "0.2.0", "BETA = 1\n")
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1", _matching_release(alpha))
    index.queue("lfx-beta", "0.2.0", None)
    published: list[Path] = []

    def publisher(path: Path) -> PublishResult:
        published.append(path)
        index.queue("lfx-beta", "0.2.0", _matching_release(beta))
        return PublishResult(0, "uploaded")

    result = publish_artifacts(
        [alpha, beta],
        index,
        publisher=publisher,
        publish_delay=0,
        verify_delay=0,
        sleep=lambda _: None,
    )

    assert published == [beta]
    assert all(entry.state == "matching" for entry in result)


def test_existing_version_with_different_source_fails_actionably(tmp_path: Path) -> None:
    local = _make_wheel(tmp_path, "lfx-alpha", "0.1.1", "VALUE = 'new'\n")
    published_dir = tmp_path / "published"
    published_dir.mkdir()
    published = _make_wheel(published_dir, "lfx-alpha", "0.1.1", "VALUE = 'old'\n")
    url = "https://files.example/lfx_alpha-0.1.1-py3-none-any.whl"
    index = FakeIndex()
    index.downloads[url] = published.read_bytes()
    index.queue(
        "lfx-alpha",
        "0.1.1",
        {"urls": [{"packagetype": "bdist_wheel", "url": url, "digests": {"sha256": "different"}}]},
    )

    with pytest.raises(PlanError, match=r"lfx-alpha 0\.1\.1: public artifact does not match.*bump lfx-alpha"):
        publish_artifacts([local], index, sleep=lambda _: None)


def test_public_index_delay_is_polled_before_success(tmp_path: Path) -> None:
    wheel = _make_wheel(tmp_path, "lfx-alpha", "0.1.1rc0", "VALUE = 1\n")
    artifact = read_wheel(wheel)
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1rc0", None, None, _matching_release(wheel))
    sleeps: list[float] = []

    result = wait_for_artifacts([artifact], index, attempts=3, delay=7, sleep=sleeps.append)

    assert result[0].state == "matching"
    assert sleeps == [7, 7]
