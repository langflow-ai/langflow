"""Tests for content-aware bundle release planning and publication."""

# ruff: noqa: S603

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bundle_release_plan import (
    BASE_DIR,
    PlanError,
    PublishResult,
    PyPIClient,
    _admits_lfx_series,
    _lfx_range_is_compatible,
    _lfx_series_admission,
    _lfx_specifiers,
    build_artifact_plan,
    build_change_plan,
    bump_version,
    check_plan_against_index,
    ensure_unpublished_bundles_fit_lfx_line,
    publish_artifacts,
    read_wheel,
    restamp_nightly_bundles,
    restamp_unpublished_bundles,
    restamp_version,
    update_changed_bundles,
    wait_for_artifacts,
    wheel_content_digest,
)


@pytest.mark.parametrize(
    "pyproject",
    sorted((BASE_DIR / "src" / "bundles").glob("*/pyproject.toml")),
    ids=lambda path: path.parent.name,
)
def test_bundle_build_backend_is_reproducibly_pinned(pyproject: Path) -> None:
    build_system = tomllib.loads(pyproject.read_text(encoding="utf-8"))["build-system"]

    assert build_system["build-backend"] == "hatchling.build"
    assert build_system["requires"] == ["hatchling==1.31.0"]


class FakeIndex:
    """Deterministic package-index fake with optional delayed responses."""

    def __init__(self) -> None:
        self.releases: dict[tuple[str, str], list[dict[str, Any] | None]] = defaultdict(list)
        self.latest_versions: dict[str, str] = {}
        self.versions: dict[str, tuple[str, ...]] = {}
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

    def get_latest_version(self, package: str) -> str | None:
        return self.latest_versions.get(package)

    def get_versions(self, package: str) -> tuple[str, ...]:
        return self.versions.get(package, ())

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
        tests_dir = package_dir / "tests"
        source_dir.mkdir(parents=True)
        tests_dir.mkdir()
        (package_dir / "pyproject.toml").write_text(_bundle_pyproject(name, version), encoding="utf-8")
        (package_dir / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        (tests_dir / "test_component.py").write_text("VALUE = 1\n", encoding="utf-8")
        (source_dir / "component.py").write_text("VALUE = 1\n", encoding="utf-8")
        (source_dir / "extension.json").write_text(
            json.dumps(
                {
                    "id": name,
                    "version": version,
                    "name": name,
                    "lfx": {"compat": ["1"]},
                    "bundles": [{"name": directory, "path": directory}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
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


def _make_wheel(
    tmp_path: Path,
    package: str,
    version: str,
    payload: str,
    *,
    metadata_version: str = "2.3",
    lfx_requirement: str = "lfx<2,>=1.11.0.dev0",
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    normalized = package.replace("-", "_")
    wheel_path = tmp_path / f"{normalized}-{version}-py3-none-any.whl"
    dist_info = f"{normalized}-{version}.dist-info"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(f"{normalized}/component.py", payload)
        wheel.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: {metadata_version}\n"
            f"Name: {package}\n"
            f"Version: {version}\n"
            f"Requires-Dist: {lfx_requirement}\n\n",
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


def test_normalized_wheel_digest_ignores_only_metadata_format_version(tmp_path: Path) -> None:
    metadata_24 = _make_wheel(tmp_path / "metadata-24", "lfx-alpha", "0.1.0", "same", metadata_version="2.4")
    metadata_25 = _make_wheel(tmp_path / "metadata-25", "lfx-alpha", "0.1.0", "same", metadata_version="2.5")
    changed_requirement = _make_wheel(
        tmp_path / "changed-requirement",
        "lfx-alpha",
        "0.1.0",
        "same",
        metadata_version="2.5",
        lfx_requirement="lfx<3,>=1.11.0.dev0",
    )

    assert hashlib.sha256(metadata_24.read_bytes()).digest() != hashlib.sha256(metadata_25.read_bytes()).digest()
    assert wheel_content_digest(metadata_24) == wheel_content_digest(metadata_25)
    assert wheel_content_digest(metadata_24) != wheel_content_digest(changed_requirement)


def test_noop_ignores_bundle_docs_and_tests(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    (repo / "src" / "bundles" / "alpha" / "README.md").write_text("docs only\n", encoding="utf-8")
    (repo / "src" / "bundles" / "alpha" / "tests" / "test_component.py").write_text("VALUE = 2\n", encoding="utf-8")

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


def test_reproducible_hatchling_pin_does_not_force_package_release(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    pyproject = repo / "src" / "bundles" / "alpha" / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + '\n[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n',
        encoding="utf-8",
    )
    _run(repo, "git", "add", ".")
    _run(repo, "git", "commit", "-qm", "add unpinned build backend")
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace('requires = ["hatchling"]', 'requires = ["hatchling==1.31.0"]'),
        encoding="utf-8",
    )

    assert build_change_plan("HEAD", base_dir=repo) == ()


def test_hatchling_pin_does_not_hide_other_pyproject_changes(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    pyproject = repo / "src" / "bundles" / "alpha" / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + '\n[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n',
        encoding="utf-8",
    )
    _run(repo, "git", "add", ".")
    _run(repo, "git", "commit", "-qm", "add unpinned build backend")
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        .replace('requires = ["hatchling"]', 'requires = ["hatchling==1.31.0"]')
        .replace('dependencies = ["lfx>=1.11.0.dev0,<2.0.0"]', 'dependencies = ["lfx>=1.11.0.dev0,<2.0.0", "httpx"]'),
        encoding="utf-8",
    )

    plan = build_change_plan("HEAD", base_dir=repo)

    assert len(plan) == 1
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


@pytest.mark.parametrize(
    ("specifier", "compatible"),
    [
        (">=1.12.0.dev0,<2.0.0", True),
        (">=1.12.4,<2.0.0", True),
        (">=1.12.4,<1.13", True),
        (">=1.11.9,<2.0.0", False),
        (">=1.12.5,<2.0.0", False),
        (">=1.12.4,<1.12.4", False),
        (">=1.12.4", False),
    ],
)
def test_lfx_range_accepts_only_installable_tightenings(specifier: str, *, compatible: bool) -> None:
    assert _lfx_range_is_compatible(specifier, "1.12.4") is compatible


def test_bundle_update_preserves_a_tightened_lfx_floor(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    pyproject = repo / "src" / "bundles" / "alpha" / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace("lfx>=1.11.0.dev0", "lfx>=1.11.0"),
        encoding="utf-8",
    )
    source = repo / "src" / "bundles" / "alpha" / "src" / "lfx_alpha" / "component.py"
    source.write_text("VALUE = 2\n", encoding="utf-8")

    plan = update_changed_bundles("HEAD", base_dir=repo, run_lock=lambda: _refresh_lock(repo))

    assert all(not entry.errors for entry in plan)
    assert '"lfx>=1.11.0,<2.0.0"' in pyproject.read_text(encoding="utf-8")


def test_prerelease_versions_share_the_requested_restamp() -> None:
    assert restamp_version("0.3.0", "rc4") == "0.3.0rc4"
    assert bump_version("0.2.9", prerelease="rc0") == "0.2.10rc0"
    assert bump_version("1.2.3", bump="minor", prerelease=".dev7") == "1.3.0.dev7"


def test_nightly_restamps_only_bundles_requiring_the_matching_final_runtime(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1", "beta": "0.2.0"})
    beta_path = repo / "src/bundles/beta/pyproject.toml"
    beta_path.write_text(beta_path.read_text().replace("lfx>=1.11.0.dev0,<2.0.0", "lfx>=1.11.0,<1.12"))
    alpha_path = repo / "src/bundles/alpha/pyproject.toml"
    alpha_before = alpha_path.read_bytes()

    plan = restamp_nightly_bundles("1.11.0.dev7", base_dir=repo)

    assert [(entry.package, entry.build_version, entry.lfx_range) for entry in plan] == [
        ("lfx-beta", "0.2.0.dev7", "==1.11.0.dev7"),
    ]
    assert alpha_path.read_bytes() == alpha_before
    beta = tomllib.loads(beta_path.read_text())["project"]
    assert beta["version"] == "0.2.0.dev7"
    assert beta["dependencies"] == ["lfx==1.11.0.dev7"]
    manifest = json.loads((repo / "src/bundles/beta/src/lfx_beta/extension.json").read_text())
    assert manifest["version"] == beta["version"]
    root = tomllib.loads((repo / "pyproject.toml").read_text())["project"]
    assert "lfx-beta>=0.2.0.dev7,<1.0.0" in root["dependencies"]
    assert restamp_nightly_bundles("1.11.0.dev7", base_dir=repo) == ()


@pytest.mark.parametrize("requirement", ["lfx>=1.11.1,<2.0.0", "lfx>=1.12.0,<2.0.0", "lfx>=1.10.0,<1.11"])
def test_nightly_does_not_lower_other_release_floors_or_partially_update(tmp_path: Path, requirement: str) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1", "beta": "0.2.0"})
    for directory, replacement in [("alpha", "lfx>=1.11.0,<2.0.0"), ("beta", requirement)]:
        path = repo / f"src/bundles/{directory}/pyproject.toml"
        path.write_text(path.read_text().replace("lfx>=1.11.0.dev0,<2.0.0", replacement))
    paths = [repo / "pyproject.toml", *(repo / "src/bundles").rglob("*.toml"), *(repo / "src/bundles").rglob("*.json")]
    originals = {path: path.read_bytes() for path in paths}

    with pytest.raises(PlanError, match="cannot restamp"):
        restamp_nightly_bundles("1.11.0.dev7", base_dir=repo)

    assert {path: path.read_bytes() for path in paths} == originals


@pytest.mark.parametrize("version", ["1.11.0", "1.11.0rc1"])
def test_nightly_requires_a_development_runtime_version(tmp_path: Path, version: str) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1"})
    with pytest.raises(PlanError, match="development version"):
        restamp_nightly_bundles(version, base_dir=repo)


@pytest.mark.parametrize("minimum", ["1.11.0.dev0", "1.11.0"])
def test_prerelease_restamp_reuses_stable_and_changes_only_unpublished_bundle(tmp_path: Path, minimum: str) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1", "beta": "0.2.0"})
    beta_path = repo / "src/bundles/beta/pyproject.toml"
    beta_path.write_text(beta_path.read_text().replace("lfx>=1.11.0.dev0", f"lfx>={minimum}"))
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1", _release_requiring("lfx<2.0.0,>=1.11.0.dev0"))
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
    beta_manifest = json.loads((repo / "src" / "bundles" / "beta" / "src" / "lfx_beta" / "extension.json").read_text())
    assert beta_manifest["version"] == "0.2.0rc3"


def test_prerelease_restamp_rejects_source_version_behind_public_latest(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1"})
    index = FakeIndex()
    index.latest_versions["lfx-alpha"] = "0.1.2"
    index.queue("lfx-alpha", "0.1.1", {"urls": [{"packagetype": "bdist_wheel"}]})

    with pytest.raises(
        PlanError,
        match=r"lfx-alpha 0\.1\.1: source version trails public version 0\.1\.2 \(lfx range unknown\)",
    ):
        restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    assert 'version = "0.1.1"' in (repo / "src" / "bundles" / "alpha" / "pyproject.toml").read_text()


def _release_requiring(lfx_requirement: str) -> dict[str, Any]:
    return {"info": {"requires_dist": ["requests>=2", lfx_requirement]}, "urls": []}


def _publish_releases(index: FakeIndex, package: str, releases: dict[str, str]) -> None:
    """Expose ``version -> lfx requirement`` releases of ``package`` on the fake index."""
    index.versions[package] = tuple(releases)
    for version, lfx_requirement in releases.items():
        index.queue(package, version, _release_requiring(lfx_requirement))


def test_prerelease_restamp_ignores_newer_release_for_another_lfx_line(tmp_path: Path) -> None:
    # The lfx 1.12 line publishes 0.2.x; the lfx 1.11 line's 0.1.x can never resolve to it.
    repo = _create_repository(tmp_path, {"alpha": "0.1.1"})
    index = FakeIndex()
    index.latest_versions["lfx-alpha"] = "0.2.0"
    index.versions["lfx-alpha"] = ("0.1.0", "0.1.1", "0.2.0rc1", "0.2.0")
    index.queue("lfx-alpha", "0.2.0", _release_requiring("lfx<2.0.0,>=1.12.0.dev0"))
    index.queue("lfx-alpha", "0.2.0rc1", _release_requiring("lfx (<2.0.0,>=1.12.0rc1)"))
    index.queue("lfx-alpha", "0.1.1", _release_requiring("lfx (<2.0.0,>=1.11.0.dev0)"))

    plan = restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    assert [(entry.package, entry.build_version, entry.action) for entry in plan] == [
        ("lfx-alpha", "0.1.1", "reuse-stable"),
    ]


def test_prerelease_restamp_ignores_newer_nightly_pinned_to_another_lfx_line(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.2.5"})
    index = FakeIndex()
    index.latest_versions["lfx-alpha"] = "0.3.2"
    index.versions["lfx-alpha"] = ("0.2.5", "0.3.2", "0.3.3.dev47")
    index.queue("lfx-alpha", "0.3.2", _release_requiring("lfx>=1.13.0.dev0,<2.0.0"))
    index.queue("lfx-alpha", "0.3.3.dev47", _release_requiring("lfx==1.13.0.dev47"))

    plan = restamp_unpublished_bundles(0, "1.12.7rc0", index, base_dir=repo)

    assert [(entry.package, entry.build_version, entry.action) for entry in plan] == [
        ("lfx-alpha", "0.2.5rc0", "publish-prerelease"),
    ]


def test_prerelease_restamp_rejects_newer_release_for_the_same_lfx_line(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1"})
    index = FakeIndex()
    index.latest_versions["lfx-alpha"] = "0.2.0"
    index.versions["lfx-alpha"] = ("0.1.1", "0.1.2", "0.2.0")
    index.queue("lfx-alpha", "0.2.0", _release_requiring("lfx<2.0.0,>=1.12.0.dev0"))
    index.queue("lfx-alpha", "0.1.2", _release_requiring("lfx<2.0.0,>=1.11.0.dev0"))

    with pytest.raises(
        PlanError,
        match=r"lfx-alpha 0\.1\.1: source version trails public version 0\.1\.2 \(lfx<2\.0\.0,>=1\.11\.0\.dev0\)",
    ):
        restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)


def test_prerelease_restamp_rejects_reusing_a_release_published_for_another_lfx_line(tmp_path: Path) -> None:
    # The lfx 1.12 line already published 0.1.8, so the lfx 1.11 line cannot reuse that number.
    repo = _create_repository(tmp_path, {"alpha": "0.2.0", "beta": "0.1.8"})
    index = FakeIndex()
    index.queue("lfx-alpha", "0.2.0", None)
    index.latest_versions["lfx-beta"] = "0.1.8"
    index.queue("lfx-beta", "0.1.8", _release_requiring("lfx (<2.0.0,>=1.12.0.dev0)"))

    with pytest.raises(
        PlanError,
        match=r"lfx-beta 0\.1\.8: already published for lfx<2\.0\.0,>=1\.12\.0\.dev0, which excludes lfx 1\.11\.0rc3",
    ):
        restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    # alpha was restamped before beta failed; the whole plan rolls back.
    assert 'version = "0.2.0"' in (repo / "src" / "bundles" / "alpha" / "pyproject.toml").read_text()


def test_prerelease_restamp_rejects_reusing_a_release_with_unknown_lfx_range(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.1"})
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1", {"urls": [{"packagetype": "bdist_wheel"}]})

    with pytest.raises(PlanError, match=r"lfx-alpha 0\.1\.1: already published for lfx range unknown"):
        restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)


@pytest.mark.parametrize("lfx_requirement", ["lfx==1.11.0", "lfx~=1.12.0", "lfx"])
def test_prerelease_restamp_rejects_reusing_a_release_whose_lfx_range_cannot_be_evaluated(
    tmp_path: Path, lfx_requirement: str
) -> None:
    # The newer-release guard treats these as admitting so it blocks; reuse must not treat them as safe.
    repo = _create_repository(tmp_path, {"alpha": "0.1.1"})
    index = FakeIndex()
    index.queue("lfx-alpha", "0.1.1", _release_requiring(lfx_requirement))

    with pytest.raises(
        PlanError,
        match=r"lfx-alpha 0\.1\.1: already published for .*, which this check cannot confirm admits lfx 1\.11\.0rc3",
    ):
        restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)


@pytest.mark.parametrize(
    ("specifier", "admission"),
    [
        (">=1.12.0.dev0,<2.0.0", True),
        ("<2.0.0,>=1.13.0.dev0", False),
        ("==1.13.0", False),
        ("==1.13.0.dev47", False),
        ("==1.11.9", False),
        ("==1.12.0", None),
        ("==1.12.4", None),
        ("==1.12.*", None),
        ("===1.13.0", None),
        ("~=1.12.0", None),
        ("!=1.12.4", None),
        ("", None),  # A bare ``lfx`` requirement.
        ("==1.11.5,<1.12.0.dev0", False),  # An excluding bound wins over an unevaluable clause.
        (">=1.12.0.dev0,==1.12.4", None),
    ],
)
def test_lfx_series_admission_reports_unevaluable_ranges(specifier: str, *, admission: bool | None) -> None:
    assert _lfx_series_admission(specifier, "1.12.4") is admission


@pytest.mark.parametrize(
    ("specifier", "admits"),
    [
        ("<2.0.0,>=1.13.0.dev0", False),
        (">=1.12.0.dev0,<2.0.0", True),
        (">=1.12.4rc0,<2.0.0", True),
        (">1.12.9", True),
        (">=1.11.0,<1.12.0.dev0", False),
        ("<=1.11.9", False),
        (">=1.10,<2", True),
        ("~=1.13.0", True),  # No comparable bound: admit so the guard fails closed.
    ],
)
def test_lfx_series_admission(specifier: str, *, admits: bool) -> None:
    assert _admits_lfx_series(specifier, "1.12.4") is admits


def test_lfx_specifiers_skip_conditional_and_unrelated_requirements() -> None:
    assert _lfx_specifiers(
        ["requests>=2", "lfx (<2.0.0,>=1.13.0.dev0)", 'lfx>=1.0; extra == "dev"', "lfx-google>=0.2"]
    ) == ("<2.0.0,>=1.13.0.dev0",)


def test_pypi_versions_exclude_yanked_and_empty_releases(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "info": {"version": "0.3.0"},
        "releases": {
            "0.2.4": [{"yanked": False}],
            "0.2.5": [{"yanked": True}],
            "0.2.6": [],
            "0.3.0": [{"yanked": True}, {"yanked": False}],
        },
    }
    monkeypatch.setattr(
        "bundle_release_plan.urllib.request.urlopen",
        lambda *_args, **_kwargs: io.BytesIO(json.dumps(payload).encode()),
    )

    assert PyPIClient().get_versions("lfx-google") == ("0.2.4", "0.3.0")


def test_prerelease_restamp_updates_runtime_lfx_requirement_not_quoted_comment(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    pyproject = repo / "src" / "bundles" / "alpha" / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        content.replace(
            'dependencies = ["lfx>=1.11.0.dev0,<2.0.0"]',
            '# Example compatibility range: "lfx>=1.10.0.dev0,<2.0.0"\ndependencies = ["lfx>=1.11.0.dev0,<2.0.0"]',
        ),
        encoding="utf-8",
    )
    index = FakeIndex()

    restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    updated = pyproject.read_text(encoding="utf-8")
    assert '# Example compatibility range: "lfx>=1.10.0.dev0,<2.0.0"' in updated
    assert 'dependencies = ["lfx>=1.11.0rc3,<2.0.0"]' in updated


def test_prerelease_restamp_updates_dependency_not_identical_description(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    pyproject = repo / "src" / "bundles" / "alpha" / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        content.replace(
            'version = "0.1.0"',
            'version = "0.1.0"\ndescription = "lfx>=1.11.0.dev0,<2.0.0"',
        ),
        encoding="utf-8",
    )
    index = FakeIndex()

    restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    updated = pyproject.read_text(encoding="utf-8")
    assert 'description = "lfx>=1.11.0.dev0,<2.0.0"' in updated
    assert 'dependencies = ["lfx>=1.11.0rc3,<2.0.0"]' in updated


def test_prerelease_restamp_preserves_lfx_extras_and_environment_marker(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0"})
    pyproject = repo / "src" / "bundles" / "alpha" / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        content.replace(
            "lfx>=1.11.0.dev0,<2.0.0",
            "lfx[cli]>=1.11.0.dev0,<2.0.0; python_version >= '3.10'",
        ),
        encoding="utf-8",
    )
    index = FakeIndex()

    restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    updated = pyproject.read_text(encoding="utf-8")
    assert "\"lfx[cli]>=1.11.0rc3,<2.0.0; python_version >= '3.10'\"" in updated


def test_prerelease_restamp_rolls_back_all_files_on_late_failure(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.1.0", "beta": "0.2.0"})
    index = FakeIndex()
    alpha_dir = repo / "src" / "bundles" / "alpha"
    beta_dir = repo / "src" / "bundles" / "beta"
    paths = [
        alpha_dir / "pyproject.toml",
        alpha_dir / "src" / "lfx_alpha" / "extension.json",
        beta_dir / "pyproject.toml",
        beta_dir / "src" / "lfx_beta" / "extension.json",
    ]
    beta_manifest = paths[-1]
    beta_manifest.write_text("{}\n", encoding="utf-8")
    originals = {path: path.read_text(encoding="utf-8") for path in paths}

    with pytest.raises(PlanError, match=r"Unable to locate extension\.json version"):
        restamp_unpublished_bundles(3, "1.11.0rc3", index, base_dir=repo)

    assert {path: path.read_text(encoding="utf-8") for path in paths} == originals


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


def test_artifact_plan_rejects_version_behind_public_latest(tmp_path: Path) -> None:
    alpha = _make_wheel(tmp_path, "lfx-alpha", "0.1.1", "ALPHA = 1\n")
    index = FakeIndex()
    index.latest_versions["lfx-alpha"] = "0.1.2"
    index.queue("lfx-alpha", "0.1.1", _matching_release(alpha))

    with pytest.raises(
        PlanError,
        match=r"lfx-alpha 0\.1\.1: source version trails public version 0\.1\.2 \(lfx range unknown\)",
    ):
        build_artifact_plan([alpha], index)


def test_artifact_plan_ignores_newer_release_for_another_lfx_line(tmp_path: Path) -> None:
    alpha = _make_wheel(tmp_path, "lfx-alpha", "0.1.1", "ALPHA = 1\n", lfx_requirement="lfx<2,>=1.11.0rc3")
    index = FakeIndex()
    index.latest_versions["lfx-alpha"] = "0.2.0"
    index.versions["lfx-alpha"] = ("0.1.1", "0.2.0")
    index.queue("lfx-alpha", "0.2.0", _release_requiring("lfx<2.0.0,>=1.12.0.dev0"))
    index.queue("lfx-alpha", "0.1.1", _matching_release(alpha))

    plan = build_artifact_plan([alpha], index)

    assert [(entry.package, entry.action) for entry in plan] == [("lfx-alpha", "reuse")]


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


def test_prerelease_restamp_rejects_a_new_version_in_an_older_lfx_lines_bundle_minor(tmp_path: Path) -> None:
    # The lfx 1.11 line published 0.2.0; a 1.12 patch in 0.2.x would race it for patch numbers.
    repo = _create_repository(tmp_path, {"alpha": "0.2.1"})
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.11.0.dev0"})

    with pytest.raises(
        PlanError,
        match=(
            r"lfx-alpha 0\.2\.1rc0: bundle minor 0\.2 is not above older lfx lines' releases "
            r"\(0\.2\.0 for lfx 1\.11\); bump lfx-alpha to 0\.3\.0 or later so lfx 1\.12 publishes"
        ),
    ):
        restamp_unpublished_bundles(0, "1.12.0rc0", index, base_dir=repo)

    assert 'version = "0.2.1"' in (repo / "src" / "bundles" / "alpha" / "pyproject.toml").read_text()


def test_prerelease_restamp_allows_a_new_version_above_older_lfx_lines_bundle_minors(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.3.0"})
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.11.0.dev0", "0.2.1": "lfx<2.0.0,>=1.12.0.dev0"})

    plan = restamp_unpublished_bundles(0, "1.12.0rc0", index, base_dir=repo)

    assert [(entry.package, entry.build_version, entry.action) for entry in plan] == [
        ("lfx-alpha", "0.3.0rc0", "publish-prerelease"),
    ]


def test_artifact_plan_rejects_an_older_line_final_that_would_replace_a_newer_lines_build(tmp_path: Path) -> None:
    # lfx 1.12 still ships 0.2.1 from the 1.11 minor, and a 1.11 final 0.2.2 admits lfx 1.12.
    alpha = _make_wheel(tmp_path, "lfx-alpha", "0.2.2", "ALPHA = 2\n")
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.11.0.dev0", "0.2.1": "lfx<2.0.0,>=1.12.0.dev0"})

    with pytest.raises(
        PlanError,
        match=(
            r"lfx-alpha 0\.2\.2: lfx<2,>=1\.11\.0\.dev0 admits lfx 1\.12, whose newest lfx-alpha is 0\.2\.1, so this "
            r"release would replace that line's build; first move lfx-alpha on the lfx 1\.12 line to a bundle minor "
            r"above 0\.2"
        ),
    ):
        build_artifact_plan([alpha], index)


@pytest.mark.parametrize(
    ("version", "lfx_requirement", "newer_releases"),
    [
        ("0.2.2", "lfx<2,>=1.11.0.dev0", {"0.2.1": "lfx<2.0.0,>=1.12.0.dev0", "0.3.0": "lfx<2.0.0,>=1.12.0.dev0"}),
        ("0.2.2", "lfx<1.12.0.dev0,>=1.11.0.dev0", {"0.2.1": "lfx<2.0.0,>=1.12.0.dev0"}),
        ("0.2.2rc1", "lfx<2,>=1.11.0rc1", {"0.2.1": "lfx<2.0.0,>=1.12.0.dev0"}),
    ],
    ids=["newer-line-moved-up", "range-excludes-newer-line", "prerelease"],
)
def test_artifact_plan_allows_an_older_line_release_that_cannot_replace_a_newer_lines_build(
    tmp_path: Path, version: str, lfx_requirement: str, newer_releases: dict[str, str]
) -> None:
    alpha = _make_wheel(tmp_path, "lfx-alpha", version, "ALPHA = 2\n", lfx_requirement=lfx_requirement)
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.11.0.dev0", **newer_releases})

    plan = build_artifact_plan([alpha], index)

    assert [(entry.package, entry.action) for entry in plan] == [("lfx-alpha", "publish")]


def test_new_version_is_blocked_by_a_release_whose_lfx_line_is_unknown(tmp_path: Path) -> None:
    alpha = _make_wheel(tmp_path, "lfx-alpha", "0.3.0", "ALPHA = 2\n")
    index = FakeIndex()
    index.versions["lfx-alpha"] = ("0.2.0", "0.3.0rc1")
    index.queue("lfx-alpha", "0.2.0", {"urls": []})
    index.queue("lfx-alpha", "0.3.0rc1", {"urls": []})

    with pytest.raises(PlanError, match=r"lfx-alpha 0\.3\.0: cannot tell which lfx line published 0\.3\.0rc1;"):
        build_artifact_plan([alpha], index)


def test_change_plan_rejects_versions_that_claim_another_lfx_lines_numbers(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.2.0", "beta": "0.3.0"})
    for directory in ("alpha", "beta"):
        source = repo / "src" / "bundles" / directory / "src" / f"lfx_{directory}" / "component.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
    plan = update_changed_bundles("HEAD", base_dir=repo, run_lock=lambda: _refresh_lock(repo))
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.10.0.dev0"})
    _publish_releases(index, "lfx-beta", {"0.3.0": "lfx<2.0.0,>=1.11.0.dev0", "0.3.1": "lfx<2.0.0,>=1.12.0.dev0"})

    errors = {entry.name: entry.errors for entry in check_plan_against_index(plan, index, base_dir=repo)}

    assert errors["lfx-alpha"] == (
        "lfx-alpha 0.2.1: bundle minor 0.2 is not above older lfx lines' releases (0.2.0 for lfx 1.10); bump "
        "lfx-alpha to 0.3.0 or later so lfx 1.11 publishes from its own bundle minor",
    )
    assert errors["lfx-beta"] == (
        "lfx-beta 0.3.1: already published for lfx<2.0.0,>=1.12.0.dev0, which excludes lfx 1.11.0; bump lfx-beta "
        "to an unpublished version in this lfx line's bundle minor before building",
    )


def test_change_plan_accepts_a_version_in_this_lfx_lines_own_bundle_minor(tmp_path: Path) -> None:
    repo = _create_repository(tmp_path, {"alpha": "0.2.0"})
    source = repo / "src" / "bundles" / "alpha" / "src" / "lfx_alpha" / "component.py"
    source.write_text("VALUE = 2\n", encoding="utf-8")
    plan = update_changed_bundles(
        "HEAD", base_dir=repo, run_lock=lambda: _refresh_lock(repo), explicit_versions={"lfx-alpha": "0.3.0"}
    )
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.10.0.dev0"})

    checked = check_plan_against_index(plan, index, base_dir=repo)

    assert [(entry.name, entry.version, entry.errors) for entry in checked] == [("lfx-alpha", "0.3.0", ())]


def test_nightly_guard_rejects_only_unpublished_versions_in_an_older_lines_bundle_minor(tmp_path: Path) -> None:
    # alpha 0.2.1 is already public, so its shared minor is history; beta 0.2.1 would be a new claim.
    repo = _create_repository(tmp_path, {"alpha": "0.2.1", "beta": "0.2.1", "gamma": "0.3.0"})
    index = FakeIndex()
    _publish_releases(index, "lfx-alpha", {"0.2.0": "lfx<2.0.0,>=1.10.0.dev0", "0.2.1": "lfx<2.0.0,>=1.11.0.dev0"})
    _publish_releases(index, "lfx-beta", {"0.2.0": "lfx<2.0.0,>=1.10.0.dev0"})
    _publish_releases(index, "lfx-gamma", {"0.2.0": "lfx<2.0.0,>=1.10.0.dev0"})

    with pytest.raises(PlanError) as raised:
        ensure_unpublished_bundles_fit_lfx_line("1.11.0.dev7", index, base_dir=repo)

    message = str(raised.value)
    assert "lfx-beta 0.2.1: bundle minor 0.2 is not above older lfx lines' releases" in message
    assert "lfx-alpha" not in message
    assert "lfx-gamma" not in message
