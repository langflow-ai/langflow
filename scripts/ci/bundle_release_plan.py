#!/usr/bin/env python3
# ruff: noqa: EM101, EM102, PERF401, PIE810, PLR2004, S603, S607, TC003, TRY003, TRY300
"""Plan, validate, restamp, publish, and verify Langflow bundle releases.

The bundle packages have their own versions, but their release metadata spans
each bundle's pyproject/manifest, Langflow's dependency floors, and uv.lock.
This module keeps those fields on one source-of-truth plan and makes PyPI
retries content-aware: an existing version is reused only when its wheel
content matches the artifact built by the current run.
"""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import tomllib

BASE_DIR = Path(__file__).resolve().parents[2]
BUNDLES_DIR = BASE_DIR / "src" / "bundles"
ROOT_PYPROJECT = BASE_DIR / "pyproject.toml"
LFX_PYPROJECT = BASE_DIR / "src" / "lfx" / "pyproject.toml"
LOCK_FILE = BASE_DIR / "uv.lock"
PYPI_BASE_URL = "https://pypi.org/pypi"

_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:(?P<pre>a|b|rc)(?P<pre_n>\d+)|\.dev(?P<dev_n>\d+))?$"
)
_REQUIREMENT_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?P<spec>.*)$")


class PlanError(RuntimeError):
    """Raised when a bundle release plan is unsafe or inconsistent."""


class IndexClient(Protocol):
    """Minimal package-index interface used by production and tests."""

    def get_release(self, package: str, version: str) -> dict[str, Any] | None:
        """Return release JSON, or None when the package/version is absent."""

    def download(self, url: str) -> bytes:
        """Download one artifact."""


@dataclass(frozen=True)
class BundleInfo:
    """Repository metadata for one bundle distribution."""

    directory: str
    name: str
    version: str
    pyproject: Path
    manifest_paths: tuple[Path, ...]
    lfx_requirement: str


@dataclass(frozen=True)
class BundleChange:
    """One bundle's entry in a repository-change release plan."""

    directory: str
    name: str
    base_version: str | None
    version: str
    source_changed: bool
    version_changed: bool
    changed_files: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class WheelArtifact:
    """Identity and reproducible-content fingerprint for a built wheel."""

    path: Path
    package: str
    version: str
    filename: str
    sha256: str
    content_digest: str


@dataclass(frozen=True)
class ArtifactObservation:
    """Comparison between one local wheel and the public package index."""

    package: str
    version: str
    filename: str
    sha256: str
    content_digest: str
    state: str
    action: str
    observed_digests: tuple[str, ...]
    remediation: str


@dataclass(frozen=True)
class PublishResult:
    """Result returned by the publisher callback."""

    returncode: int
    output: str


@dataclass(frozen=True)
class VersionTarget:
    """Ephemeral version target used while building a release candidate."""

    package: str
    source_version: str
    build_version: str
    action: str
    lfx_range: str


class PyPIClient:
    """urllib-backed public PyPI client."""

    def __init__(self, base_url: str = PYPI_BASE_URL, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_release(self, package: str, version: str) -> dict[str, Any] | None:
        url = f"{self.base_url}/{canonicalize_name(package)}/{version}/json"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:  # noqa: S310
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise PlanError(f"{package} {version}: public index returned HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise PlanError(f"{package} {version}: unable to query public index {url}: {exc.reason}") from exc

    def download(self, url: str) -> bytes:
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:  # noqa: S310
                return response.read()
        except urllib.error.URLError as exc:
            raise PlanError(f"Unable to download public artifact {url}: {exc.reason}") from exc


def canonicalize_name(name: str) -> str:
    """Return a PEP 503-style normalized distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_version(version: str) -> tuple[int, int, int, int, int]:
    """Parse the repository's supported PEP 440 release forms into a sortable key."""
    match = _VERSION_RE.fullmatch(version)
    if not match:
        raise PlanError(f"Unsupported version {version!r}; expected X.Y.Z, X.Y.Z.devN, X.Y.ZaN, X.Y.ZbN, or X.Y.ZrcN")
    release = (int(match["major"]), int(match["minor"]), int(match["patch"]))
    if match["dev_n"] is not None:
        phase = (-4, int(match["dev_n"]))
    elif match["pre"] is not None:
        phase_order = {"a": -3, "b": -2, "rc": -1}
        phase = (phase_order[match["pre"]], int(match["pre_n"]))
    else:
        phase = (0, 0)
    return (*release, *phase)


def bump_version(version: str, bump: str = "patch", prerelease: str | None = None) -> str:
    """Increment a stable release component and optionally append a prerelease label."""
    major, minor, patch, _, _ = parse_version(version)
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    elif bump == "patch":
        patch += 1
    else:
        raise PlanError(f"Unsupported bump {bump!r}; choose patch, minor, or major")
    suffix = prerelease or ""
    if suffix and not re.fullmatch(r"(?:a|b|rc)\d+|\.dev\d+", suffix):
        raise PlanError(f"Unsupported prerelease label {suffix!r}; expected rcN, aN, bN, or .devN")
    return f"{major}.{minor}.{patch}{suffix}"


def restamp_version(version: str, prerelease: str) -> str:
    """Apply a shared prerelease label to a stable source version."""
    major, minor, patch, _, _ = parse_version(version)
    if not re.fullmatch(r"(?:a|b|rc)\d+|\.dev\d+", prerelease):
        raise PlanError(f"Unsupported prerelease label {prerelease!r}")
    return f"{major}.{minor}.{patch}{prerelease}"


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _requirement_parts(requirement: str) -> tuple[str, str]:
    match = _REQUIREMENT_RE.match(requirement.strip())
    if not match:
        return "", ""
    return canonicalize_name(match["name"]), match["spec"].replace(" ", "")


def _project_version(content: str, source: str) -> str:
    data = tomllib.loads(content)
    try:
        version = str(data["project"]["version"])
    except KeyError as exc:
        raise PlanError(f"{source}: missing [project].version") from exc
    parse_version(version)
    return version


def _lfx_floor_spec(version: str) -> str:
    major, minor, _, _, _ = parse_version(version)
    return f">={major}.{minor}.0.dev0,<{major + 1}.0.0"


def _discover_bundles(base_dir: Path = BASE_DIR) -> dict[str, BundleInfo]:
    bundles: dict[str, BundleInfo] = {}
    bundles_dir = base_dir / "src" / "bundles"
    for pyproject in sorted(bundles_dir.glob("*/pyproject.toml")):
        data = _read_toml(pyproject)
        project = data["project"]
        name = canonicalize_name(str(project["name"]))
        version = str(project["version"])
        parse_version(version)
        lfx_requirements = [
            requirement
            for requirement in project.get("dependencies", [])
            if _requirement_parts(str(requirement))[0] == "lfx"
        ]
        if len(lfx_requirements) != 1:
            raise PlanError(f"{name} {version}: expected exactly one runtime lfx requirement, found {lfx_requirements}")
        manifests = tuple(sorted(pyproject.parent.glob("src/*/extension.json")))
        bundles[pyproject.parent.name] = BundleInfo(
            directory=pyproject.parent.name,
            name=name,
            version=version,
            pyproject=pyproject,
            manifest_paths=manifests,
            lfx_requirement=str(lfx_requirements[0]),
        )
    return bundles


def _git_output(args: Sequence[str], base_dir: Path = BASE_DIR) -> str:
    completed = subprocess.run(["git", *args], cwd=base_dir, check=False, capture_output=True, text=True)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PlanError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def changed_files(base_ref: str, head_ref: str | None = None, base_dir: Path = BASE_DIR) -> tuple[str, ...]:
    """List files changed from a merge base to HEAD or the current working tree."""
    comparison = f"{base_ref}...{head_ref}" if head_ref else base_ref
    return tuple(line for line in _git_output(["diff", "--name-only", comparison, "--"], base_dir).splitlines() if line)


def _git_file(ref: str, path: str, base_dir: Path = BASE_DIR) -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=base_dir, check=False, capture_output=True, text=True
    )
    if completed.returncode:
        return None
    return completed.stdout


def _release_relevant(path: str, bundle_dir: str) -> bool:
    prefix = f"src/bundles/{bundle_dir}/"
    if not path.startswith(prefix):
        return False
    relative = path.removeprefix(prefix)
    return relative == "pyproject.toml" or relative.startswith("src/")


def _root_requirements(bundle_name: str, base_dir: Path = BASE_DIR) -> tuple[str, ...]:
    data = _read_toml(base_dir / "pyproject.toml")
    project = data["project"]
    requirements: list[str] = []
    for requirement in project.get("dependencies", []):
        if _requirement_parts(str(requirement))[0] == bundle_name:
            requirements.append(str(requirement))
    for optional_requirements in project.get("optional-dependencies", {}).values():
        for requirement in optional_requirements:
            if _requirement_parts(str(requirement))[0] == bundle_name:
                requirements.append(str(requirement))
    return tuple(requirements)


def _minimum_and_upper(specifier: str) -> tuple[str | None, str | None]:
    minimum = None
    upper = None
    for part in specifier.split(","):
        if part.startswith(">="):
            minimum = part[2:]
        elif part.startswith("<"):
            upper = part[1:]
    return minimum, upper


def _lock_version(bundle_name: str, base_dir: Path = BASE_DIR) -> str | None:
    lock_data = _read_toml(base_dir / "uv.lock")
    for package in lock_data.get("package", []):
        if canonicalize_name(str(package.get("name", ""))) == bundle_name:
            return str(package.get("version"))
    return None


def _manifest_errors(bundle: BundleInfo, base_dir: Path = BASE_DIR) -> list[str]:
    errors: list[str] = []
    for manifest_path in bundle.manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        observed = str(manifest.get("version", ""))
        if observed != bundle.version:
            relative = manifest_path.relative_to(base_dir)
            errors.append(
                f"{bundle.name} {bundle.version}: {relative} declares version {observed!r}; "
                f"set it to {bundle.version!r}"
            )
    return errors


def _metadata_errors(bundle: BundleInfo, base_dir: Path = BASE_DIR) -> list[str]:
    errors = _manifest_errors(bundle, base_dir)
    lfx_version = str(_read_toml(base_dir / "src" / "lfx" / "pyproject.toml")["project"]["version"])
    expected_lfx = _lfx_floor_spec(lfx_version)
    _, observed_lfx = _requirement_parts(bundle.lfx_requirement)
    if observed_lfx != expected_lfx:
        errors.append(
            f"{bundle.name} {bundle.version}: expected lfx range {expected_lfx}, observed {observed_lfx or '<none>'}; "
            "run bundle_release_plan.py update"
        )

    root_requirements = _root_requirements(bundle.name, base_dir)
    if not root_requirements:
        errors.append(
            f"{bundle.name} {bundle.version}: no Langflow dependency range found in pyproject.toml; "
            f"add {bundle.name}>={bundle.version},<{parse_version(bundle.version)[0] + 1}.0.0"
        )
    for requirement in root_requirements:
        _, specifier = _requirement_parts(requirement)
        minimum, upper = _minimum_and_upper(specifier)
        if minimum != bundle.version or upper is None:
            errors.append(
                f"{bundle.name} {bundle.version}: expected a bounded Langflow floor >={bundle.version} in "
                f"{requirement!r}, observed {specifier or '<none>'}; run bundle_release_plan.py update"
            )

    locked = _lock_version(bundle.name, base_dir)
    if locked != bundle.version:
        errors.append(
            f"{bundle.name} {bundle.version}: uv.lock contains {locked or '<missing>'}; "
            "run bundle_release_plan.py update "
            "to regenerate the lockfile"
        )
    return errors


def build_change_plan(
    base_ref: str,
    head_ref: str | None = None,
    *,
    base_dir: Path = BASE_DIR,
    files: Iterable[str] | None = None,
) -> tuple[BundleChange, ...]:
    """Build and validate the affected-bundle plan for repository changes."""
    bundles = _discover_bundles(base_dir)
    changed = tuple(files) if files is not None else changed_files(base_ref, head_ref, base_dir)
    touched_dirs = {
        parts[2] for path in changed if len(parts := Path(path).parts) >= 4 and parts[:2] == ("src", "bundles")
    }
    plan: list[BundleChange] = []
    for directory in sorted(touched_dirs):
        bundle = bundles.get(directory)
        if bundle is None:
            raise PlanError(
                f"src/bundles/{directory}: changed bundle has no pyproject.toml; add package metadata before release"
            )
        bundle_files = tuple(path for path in changed if path.startswith(f"src/bundles/{directory}/"))
        source_changed = any(_release_relevant(path, directory) for path in bundle_files)
        relative_pyproject = str(bundle.pyproject.relative_to(base_dir))
        base_content = _git_file(base_ref, relative_pyproject, base_dir)
        base_version = _project_version(base_content, f"{base_ref}:{relative_pyproject}") if base_content else None
        version_changed = base_version != bundle.version
        if not source_changed and not version_changed:
            continue

        errors: list[str] = []
        if source_changed and base_version == bundle.version:
            errors.append(
                f"{bundle.name}: releasable source changed but version remains {bundle.version}; run "
                f"python scripts/ci/bundle_release_plan.py update --base-ref {base_ref}"
            )
        if (
            base_version is not None
            and version_changed
            and parse_version(bundle.version) <= parse_version(base_version)
        ):
            errors.append(
                f"{bundle.name}: version must increase from {base_version}, "
                f"observed {bundle.version}; choose a newer version"
            )
        if version_changed or base_version is None:
            errors.extend(_metadata_errors(bundle, base_dir))
        plan.append(
            BundleChange(
                directory=directory,
                name=bundle.name,
                base_version=base_version,
                version=bundle.version,
                source_changed=source_changed,
                version_changed=version_changed,
                changed_files=bundle_files,
                errors=tuple(errors),
            )
        )
    return tuple(plan)


def _replace_project_version(content: str, version: str) -> str:
    updated, count = re.subn(r'(?m)^version = "[^"]+"', f'version = "{version}"', content, count=1)
    if count != 1:
        raise PlanError("Unable to locate [project].version")
    return updated


def _replace_bundle_floor(content: str, bundle_name: str, version: str) -> str:
    pattern = re.compile(rf'("{re.escape(bundle_name)}(?:\[[^]"]+\])?>=)([^,<";\s]+)(,<[^";]+)(")')
    updated, count = pattern.subn(rf"\g<1>{version}\g<3>\g<4>", content)
    if count == 0:
        raise PlanError(
            f"{bundle_name} {version}: could not update a bounded >= dependency in pyproject.toml; add one explicitly"
        )
    return updated


def _replace_lfx_floor(content: str, lfx_version: str, *, exact: bool = False) -> str:
    major = parse_version(lfx_version)[0]
    expected = f">={lfx_version},<{major + 1}.0.0" if exact else _lfx_floor_spec(lfx_version)
    updated, count = re.subn(r'"lfx(?:>=|~=|==)[^"]+"', f'"lfx{expected}"', content, count=1)
    if count != 1:
        raise PlanError("Unable to locate the bundle runtime lfx requirement")
    return updated


def _replace_manifest_version(content: str, version: str) -> str:
    updated, count = re.subn(r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{version}\g<2>", content, count=1)
    if count != 1:
        raise PlanError("Unable to locate extension.json version")
    return updated


def update_changed_bundles(
    base_ref: str,
    *,
    bump: str = "patch",
    prerelease: str | None = None,
    explicit_versions: dict[str, str] | None = None,
    run_lock: Callable[[], None] | None = None,
    base_dir: Path = BASE_DIR,
) -> tuple[BundleChange, ...]:
    """Update all metadata for changed bundles and regenerate uv.lock as one operation."""
    explicit_versions = {canonicalize_name(name): version for name, version in (explicit_versions or {}).items()}
    initial_plan = build_change_plan(base_ref, base_dir=base_dir)
    affected = [entry for entry in initial_plan if entry.source_changed or entry.version_changed]
    if not affected:
        return ()
    bundles = _discover_bundles(base_dir)
    root_path = base_dir / "pyproject.toml"
    lfx_version = str(_read_toml(base_dir / "src" / "lfx" / "pyproject.toml")["project"]["version"])
    paths = {root_path, base_dir / "uv.lock"}
    for entry in affected:
        bundle = bundles[entry.directory]
        paths.add(bundle.pyproject)
        paths.update(bundle.manifest_paths)
    originals = {path: path.read_text(encoding="utf-8") for path in paths if path.exists()}

    try:
        root_content = originals[root_path]
        for entry in affected:
            bundle = bundles[entry.directory]
            if entry.name in explicit_versions:
                target_version = explicit_versions[entry.name]
                parse_version(target_version)
            elif entry.base_version is not None and parse_version(bundle.version) > parse_version(entry.base_version):
                target_version = bundle.version
            else:
                target_version = bump_version(entry.base_version or bundle.version, bump, prerelease)
            bundle_content = _replace_project_version(originals[bundle.pyproject], target_version)
            bundle_content = _replace_lfx_floor(bundle_content, lfx_version)
            bundle.pyproject.write_text(bundle_content, encoding="utf-8")
            for manifest_path in bundle.manifest_paths:
                manifest_path.write_text(
                    _replace_manifest_version(originals[manifest_path], target_version), encoding="utf-8"
                )
            root_content = _replace_bundle_floor(root_content, bundle.name, target_version)
        root_path.write_text(root_content, encoding="utf-8")
        if run_lock is None:
            completed = subprocess.run(["uv", "lock"], cwd=base_dir, check=False)
            if completed.returncode:
                raise PlanError("uv lock failed; all bundle release-plan edits were rolled back")
        else:
            run_lock()
        final_plan = build_change_plan(base_ref, base_dir=base_dir)
        errors = [error for entry in final_plan for error in entry.errors]
        if errors:
            raise PlanError("Bundle update left an invalid plan:\n" + "\n".join(f"- {error}" for error in errors))
        return final_plan
    except Exception:
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        raise


def restamp_unpublished_bundles(
    rc_number: int,
    lfx_version: str,
    client: IndexClient,
    *,
    base_dir: Path = BASE_DIR,
) -> tuple[VersionTarget, ...]:
    """Restamp only unpublished stable bundles for a shared release candidate build."""
    if rc_number < 0:
        raise PlanError("RC number must be non-negative")
    parse_version(lfx_version)
    bundles = _discover_bundles(base_dir)
    paths = {path for bundle in bundles.values() for path in (bundle.pyproject, *bundle.manifest_paths)}
    originals = {path: path.read_text(encoding="utf-8") for path in paths}
    targets: list[VersionTarget] = []
    try:
        for bundle in bundles.values():
            if client.get_release(bundle.name, bundle.version) is not None:
                targets.append(
                    VersionTarget(
                        package=bundle.name,
                        source_version=bundle.version,
                        build_version=bundle.version,
                        action="reuse-stable",
                        lfx_range=_requirement_parts(bundle.lfx_requirement)[1],
                    )
                )
                continue
            target_version = restamp_version(bundle.version, f"rc{rc_number}")
            bundle_content = _replace_project_version(originals[bundle.pyproject], target_version)
            bundle_content = _replace_lfx_floor(bundle_content, lfx_version, exact=True)
            bundle.pyproject.write_text(bundle_content, encoding="utf-8")
            for manifest_path in bundle.manifest_paths:
                manifest_path.write_text(
                    _replace_manifest_version(originals[manifest_path], target_version),
                    encoding="utf-8",
                )
            targets.append(
                VersionTarget(
                    package=bundle.name,
                    source_version=bundle.version,
                    build_version=target_version,
                    action="publish-prerelease",
                    lfx_range=f">={lfx_version},<{parse_version(lfx_version)[0] + 1}.0.0",
                )
            )
        return tuple(sorted(targets, key=lambda item: item.package))
    except Exception:
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        raise


def wheel_content_digest(source: Path | bytes) -> str:
    """Hash wheel payload and METADATA while ignoring build-tool bookkeeping."""
    if isinstance(source, Path):
        wheel: zipfile.ZipFile[Any] = zipfile.ZipFile(source)
    else:
        import io

        wheel = zipfile.ZipFile(io.BytesIO(source))
    digest = hashlib.sha256()
    with wheel:
        for name in sorted(wheel.namelist()):
            if name.endswith((".dist-info/RECORD", ".dist-info/WHEEL")) or name.endswith("/"):
                continue
            payload = wheel.read(name)
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(str(len(payload)).encode())
            digest.update(b"\0")
            digest.update(payload)
    return digest.hexdigest()


def read_wheel(path: Path) -> WheelArtifact:
    """Read package identity and both byte-level and normalized wheel digests."""
    with zipfile.ZipFile(path) as wheel:
        metadata_paths = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise PlanError(f"{path}: expected one .dist-info/METADATA file, found {len(metadata_paths)}")
        metadata = email.message_from_bytes(wheel.read(metadata_paths[0]))
    package = canonicalize_name(str(metadata["Name"]))
    version = str(metadata["Version"])
    parse_version(version)
    return WheelArtifact(
        path=path,
        package=package,
        version=version,
        filename=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        content_digest=wheel_content_digest(path),
    )


def observe_artifact(artifact: WheelArtifact, client: IndexClient) -> ArtifactObservation:
    """Compare one local artifact with the public package index."""
    release = client.get_release(artifact.package, artifact.version)
    if release is None:
        return ArtifactObservation(
            package=artifact.package,
            version=artifact.version,
            filename=artifact.filename,
            sha256=artifact.sha256,
            content_digest=artifact.content_digest,
            state="missing",
            action="publish",
            observed_digests=(),
            remediation=f"publish {artifact.package} {artifact.version}, then wait for public-index propagation",
        )

    urls = release.get("urls", [])
    wheel_urls = [item for item in urls if item.get("packagetype") == "bdist_wheel"]
    for item in wheel_urls:
        published_sha = str(item.get("digests", {}).get("sha256", ""))
        if published_sha and published_sha == artifact.sha256:
            return ArtifactObservation(
                package=artifact.package,
                version=artifact.version,
                filename=artifact.filename,
                sha256=artifact.sha256,
                content_digest=artifact.content_digest,
                state="matching",
                action="reuse",
                observed_digests=(published_sha,),
                remediation="none; the matching artifact is already public",
            )

    observed: list[str] = []
    for item in wheel_urls:
        url = str(item.get("url", ""))
        if not url:
            continue
        published_content_digest = wheel_content_digest(client.download(url))
        observed.append(published_content_digest)
        if published_content_digest == artifact.content_digest:
            return ArtifactObservation(
                package=artifact.package,
                version=artifact.version,
                filename=artifact.filename,
                sha256=artifact.sha256,
                content_digest=artifact.content_digest,
                state="matching",
                action="reuse",
                observed_digests=tuple(observed),
                remediation="none; normalized wheel content matches the public artifact",
            )

    return ArtifactObservation(
        package=artifact.package,
        version=artifact.version,
        filename=artifact.filename,
        sha256=artifact.sha256,
        content_digest=artifact.content_digest,
        state="mismatch",
        action="fail",
        observed_digests=tuple(observed),
        remediation=(
            f"bump {artifact.package} above {artifact.version}, update its Langflow dependency floor and uv.lock, "
            "then rebuild; PyPI versions are immutable"
        ),
    )


def build_artifact_plan(paths: Sequence[Path], client: IndexClient) -> tuple[ArtifactObservation, ...]:
    """Return deterministic public-index observations for built wheels."""
    artifacts = sorted((read_wheel(path) for path in paths), key=lambda item: (item.package, item.version))
    return tuple(observe_artifact(artifact, client) for artifact in artifacts)


def _mismatch_message(observation: ArtifactObservation) -> str:
    observed = ", ".join(observation.observed_digests) or "no comparable wheel content"
    return (
        f"{observation.package} {observation.version}: public artifact does not match the current source. "
        f"Expected content digest {observation.content_digest}; observed {observed}. "
        f"Remediation: {observation.remediation}."
    )


def wait_for_artifacts(
    artifacts: Sequence[WheelArtifact],
    client: IndexClient,
    *,
    attempts: int,
    delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[ArtifactObservation, ...]:
    """Poll until every artifact is public and content-matching."""
    if attempts < 1:
        raise PlanError("verify attempts must be at least 1")
    latest: tuple[ArtifactObservation, ...] = ()
    for attempt in range(1, attempts + 1):
        latest = tuple(observe_artifact(artifact, client) for artifact in artifacts)
        mismatches = [item for item in latest if item.state == "mismatch"]
        if mismatches:
            raise PlanError("\n".join(_mismatch_message(item) for item in mismatches))
        missing = [item for item in latest if item.state == "missing"]
        if not missing:
            return latest
        if attempt < attempts:
            labels = ", ".join(f"{item.package} {item.version}" for item in missing)
            print(f"Public index has not exposed {labels}; retrying in {delay:g}s ({attempt}/{attempts}).")
            sleep(delay)
    details = "; ".join(
        f"{item.package} {item.version} missing (expected range/artifact from {item.filename})" for item in latest
    )
    raise PlanError(
        f"Public-index propagation timed out after {attempts} attempts: {details}. "
        "Remediation: confirm the PyPI upload succeeded, then rerun after the version appears."
    )


def _default_publisher(path: Path) -> PublishResult:
    completed = subprocess.run(["uv", "publish", str(path)], check=False, capture_output=True, text=True)
    return PublishResult(completed.returncode, f"{completed.stdout}\n{completed.stderr}".strip())


def publish_artifacts(
    paths: Sequence[Path],
    client: IndexClient,
    *,
    publisher: Callable[[Path], PublishResult] = _default_publisher,
    publish_attempts: int = 5,
    publish_delay: float = 60,
    verify_attempts: int = 10,
    verify_delay: float = 30,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[ArtifactObservation, ...]:
    """Idempotently publish missing wheels, rejecting immutable-version mismatches."""
    artifacts = sorted((read_wheel(path) for path in paths), key=lambda item: (item.package, item.version))
    initial = tuple(observe_artifact(artifact, client) for artifact in artifacts)
    mismatches = [item for item in initial if item.state == "mismatch"]
    if mismatches:
        raise PlanError("\n".join(_mismatch_message(item) for item in mismatches))
    missing_names = {(item.package, item.version) for item in initial if item.state == "missing"}
    missing = [artifact for artifact in artifacts if (artifact.package, artifact.version) in missing_names]

    for index, artifact in enumerate(missing):
        for attempt in range(1, publish_attempts + 1):
            print(f"Publishing {artifact.package} {artifact.version} from {artifact.path}")
            result = publisher(artifact.path)
            if result.output:
                print(result.output)
            if result.returncode == 0:
                break
            lowered = result.output.lower()
            if any(marker in lowered for marker in ("already exists", "file already exists", "duplicate")):
                break
            rate_limited = any(
                marker in lowered for marker in ("http 429", "429 too many requests", "too many new projects created")
            )
            if rate_limited and attempt < publish_attempts:
                print(
                    f"PyPI rate limited {artifact.package} {artifact.version}; retrying in {publish_delay:g}s "
                    f"({attempt}/{publish_attempts})."
                )
                sleep(publish_delay)
                continue
            raise PlanError(
                f"{artifact.package} {artifact.version}: publish failed after attempt {attempt}/{publish_attempts}. "
                f"Remediation: inspect the uv publish output, correct credentials/rate limits, and rerun. Output: "
                f"{result.output.strip()}"
            )
        if index < len(missing) - 1:
            sleep(publish_delay)
    return wait_for_artifacts(artifacts, client, attempts=verify_attempts, delay=verify_delay, sleep=sleep)


def _plan_payload(plan: Sequence[BundleChange]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "invalid" if any(entry.errors for entry in plan) else "ready",
        "bundles": [asdict(entry) for entry in plan],
    }


def _artifact_payload(plan: Sequence[ArtifactObservation]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "invalid" if any(entry.state == "mismatch" for entry in plan) else "ready",
        "artifacts": [asdict(entry) for entry in plan],
    }


def _version_payload(plan: Sequence[VersionTarget]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "ready",
        "bundles": [asdict(entry) for entry in plan],
    }


def _write_json(payload: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def _print_change_summary(plan: Sequence[BundleChange]) -> None:
    if not plan:
        print("Bundle release plan: no releasable bundle changes.")
        return
    print("Bundle release plan:")
    for entry in plan:
        previous = entry.base_version or "new"
        status = "invalid" if entry.errors else "ready"
        print(f"- {entry.name}: {previous} -> {entry.version} ({status})")
        for error in entry.errors:
            print(f"  ERROR: {error}")


def _parse_explicit_versions(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise PlanError(f"Invalid --version {value!r}; expected package=version")
        package, version = value.split("=", 1)
        parse_version(version)
        result[canonicalize_name(package)] = version
    return result


def _glob_wheels(values: Sequence[str]) -> list[Path]:
    paths = [Path(value) for value in values]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise PlanError(f"Wheel files not found: {', '.join(missing)}")
    if not paths:
        raise PlanError("No wheel artifacts supplied")
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="generate and validate the changed-bundle release plan")
    plan.add_argument("--base-ref", required=True)
    plan.add_argument("--head-ref")
    plan.add_argument("--output", type=Path)
    plan.add_argument("--check", action="store_true")

    update = subparsers.add_parser("update", help="atomically bump changed bundles and all dependent metadata")
    update.add_argument("--base-ref", required=True)
    update.add_argument("--bump", choices=("patch", "minor", "major"), default="patch")
    update.add_argument("--prerelease")
    update.add_argument("--version", action="append", default=[], metavar="PACKAGE=VERSION")
    update.add_argument("--output", type=Path)

    restamp = subparsers.add_parser(
        "restamp", help="apply one content-aware prerelease version plan to unpublished stable bundles"
    )
    restamp.add_argument("--rc-number", required=True, type=int)
    restamp.add_argument("--lfx-version", required=True)
    restamp.add_argument("--output", type=Path)

    artifacts = subparsers.add_parser("artifacts", help="dry-run a content-aware public-index artifact plan")
    artifacts.add_argument("wheels", nargs="+")
    artifacts.add_argument("--output", type=Path)

    publish = subparsers.add_parser("publish", help="publish missing artifacts and verify public propagation")
    publish.add_argument("wheels", nargs="+")
    publish.add_argument("--publish-attempts", type=int, default=5)
    publish.add_argument("--publish-delay", type=float, default=60)
    publish.add_argument("--verify-attempts", type=int, default=10)
    publish.add_argument("--verify-delay", type=float, default=30)
    publish.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="wait for exact built artifacts on the public index")
    verify.add_argument("wheels", nargs="+")
    verify.add_argument("--attempts", type=int, default=10)
    verify.add_argument("--delay", type=float, default=30)
    verify.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            plan = build_change_plan(args.base_ref, args.head_ref)
            _print_change_summary(plan)
            _write_json(_plan_payload(plan), args.output)
            if args.check and any(entry.errors for entry in plan):
                return 1
            return 0
        if args.command == "update":
            plan = update_changed_bundles(
                args.base_ref,
                bump=args.bump,
                prerelease=args.prerelease,
                explicit_versions=_parse_explicit_versions(args.version),
            )
            _print_change_summary(plan)
            _write_json(_plan_payload(plan), args.output)
            return 0

        if args.command == "restamp":
            version_plan = restamp_unpublished_bundles(
                args.rc_number,
                args.lfx_version,
                PyPIClient(),
            )
            _write_json(_version_payload(version_plan), args.output)
            return 0

        paths = _glob_wheels(args.wheels)
        client = PyPIClient()
        if args.command == "artifacts":
            plan = build_artifact_plan(paths, client)
        elif args.command == "publish":
            plan = publish_artifacts(
                paths,
                client,
                publish_attempts=args.publish_attempts,
                publish_delay=args.publish_delay,
                verify_attempts=args.verify_attempts,
                verify_delay=args.verify_delay,
            )
        elif args.command == "verify":
            artifacts = [read_wheel(path) for path in paths]
            plan = wait_for_artifacts(artifacts, client, attempts=args.attempts, delay=args.delay)
        else:  # pragma: no cover - argparse enforces the command set
            raise PlanError(f"Unsupported command {args.command}")
        _write_json(_artifact_payload(plan), args.output)
        mismatches = [entry for entry in plan if entry.state == "mismatch"]
        if mismatches:
            for observation in mismatches:
                print(_mismatch_message(observation), file=sys.stderr)
            return 1
        return 0
    except PlanError as exc:
        print(f"Bundle release plan failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
