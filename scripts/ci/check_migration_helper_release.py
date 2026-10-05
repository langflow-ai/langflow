"""Require an authenticated, qualified helper before publishing Langflow 1.13.

The release job downloads a durable helper kit and provisions Sigstore trust
independently. This check never accepts a kit's own trust root or rebuilds it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import tomllib

IDENTITY = (
    r"^https://github\.com/langflow-ai/langflow/\.github/workflows/chroma-migration-helper\.yml"
    r"@refs/heads/release-1\.13\.0$"
)
HELPER_PATHS = (
    "tools/chroma_migration_helper",
    "src/backend/base/langflow/services/knowledge_base_storage/helper.py",
    "src/lfx/src/lfx/base/knowledge_bases/migration",
    "src/lfx/src/lfx/base/knowledge_bases/backends/sqlite.py",
    "src/lfx/src/lfx/base/knowledge_bases/backends/base.py",
    ".github/workflows/chroma-migration-helper.yml",
)
PLATFORMS = {"linux/amd64", "linux/arm64"}
MANIFESTS = ("pyproject.toml", "src/backend/base/pyproject.toml", "src/lfx/pyproject.toml")


class QualificationError(ValueError):
    """Release evidence is missing, inconsistent or unauthenticated."""


def _require(condition: bool, message: str) -> None:  # noqa: FBT001 - assertion condition, not a behavioral flag
    """Raise a qualification error when a release evidence condition fails."""
    if not condition:
        raise QualificationError(message)


def _read(path: Path) -> bytes:
    """Read release evidence bytes from the supplied path."""
    _require(not path.is_symlink() and path.is_file(), "Expected a regular release evidence file")
    _require(path.stat().st_size <= 1024 * 1024, "Release evidence exceeds its size bound")
    return path.read_bytes()


def _object(data: bytes) -> dict:
    """Decode a JSON object while rejecting duplicate fields."""

    def unique(pairs):
        """Reject duplicate keys when decoding release evidence."""
        result = {}
        for key, value in pairs:
            _require(key not in result, "Duplicate release evidence key")
            result[key] = value
        return result

    value = json.loads(data, object_pairs_hook=unique)
    _require(type(value) is dict, "Release evidence must be an object")
    return value


def validate_documents(manifest_bytes: bytes, qualification_bytes: bytes, release_tag: str) -> str:
    """Validate bindings only after both exact byte strings are authenticated."""
    manifest, qualification = _object(manifest_bytes), _object(qualification_bytes)
    _require(
        set(manifest) == {"protocol_version", "image", "reader", "security_disposition", "commit", "platforms"},
        "Unexpected helper manifest schema",
    )
    _require(
        set(qualification)
        == {
            "schema_version",
            "artifact_type",
            "helper_image",
            "source_commit",
            "release_manifest_sha256",
            "qualification_profile",
            "platforms",
        },
        "Unexpected qualification schema",
    )
    commit = manifest["commit"]
    _require(isinstance(commit, str) and re.fullmatch(r"[a-f0-9]{40}", commit) is not None, "Invalid helper commit")
    _require(release_tag == f"helper-1.13-{commit}", "Helper release tag does not match its signed source")
    _require(
        isinstance(manifest["image"], str)
        and re.fullmatch(r"ghcr\.io/langflow-ai/langflow-chroma-migration@sha256:[a-f0-9]{64}", manifest["image"])
        is not None,
        "Helper image must be an immutable dedicated registry digest",
    )
    _require(
        type(manifest["protocol_version"]) is int
        and manifest["protocol_version"] == 1
        and manifest["reader"] == "chroma-rust-1.5.9"
        and isinstance(manifest["security_disposition"], str)
        and bool(manifest["security_disposition"].strip()),
        "Helper protocol or security disposition is missing",
    )
    _require(
        type(qualification["schema_version"]) is int
        and qualification["schema_version"] == 1
        and qualification["artifact_type"] == "langflow-chroma-migration-qualification"
        and qualification["qualification_profile"] == "offline-native-reader-v1"
        and qualification["helper_image"] == manifest["image"]
        and qualification["source_commit"] == commit
        and qualification["release_manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest(),
        "Signed qualification does not bind this helper release",
    )
    _require(
        type(manifest["platforms"]) is dict
        and set(manifest["platforms"]) == PLATFORMS
        and type(qualification["platforms"]) is dict
        and set(qualification["platforms"]) == PLATFORMS,
        "Both supported helper platforms must be qualified",
    )
    for platform in sorted(PLATFORMS):
        entry, result = manifest["platforms"][platform], qualification["platforms"][platform]
        _require(
            type(entry) is dict and set(entry) == {"image_id", "content_sha256", "archive", "archive_sha256"},
            "Invalid platform manifest",
        )
        _require(
            type(result) is dict and set(result) == {"image_id", "content_sha256", "archive_sha256", "qualified"},
            "Invalid platform proof",
        )
        _require(
            isinstance(entry["image_id"], str)
            and re.fullmatch(r"sha256:[a-f0-9]{64}", entry["image_id"]) is not None
            and isinstance(entry["archive_sha256"], str)
            and re.fullmatch(r"[a-f0-9]{64}", entry["archive_sha256"]) is not None
            and entry["archive"] == f"helper-image-{platform.replace('/', '-')}.tar"
            and isinstance(entry["content_sha256"], str)
            and re.fullmatch(r"[a-f0-9]{64}", entry["content_sha256"]) is not None
            and result["content_sha256"] == entry["content_sha256"]
            and result["image_id"] == entry["image_id"]
            and result["archive_sha256"] == entry["archive_sha256"]
            and result["qualified"] is True,
            "Platform qualification does not match the signed image archive",
        )
    return commit


def _run(*args: str) -> bytes:
    """Capture a checked command's output within the release validation deadline."""
    return subprocess.run(args, check=True, capture_output=True, timeout=120).stdout  # noqa: S603


def normalize_dependencies(value: dict, workspace_versions: dict[str, set[str]]) -> dict:
    """Permit exact workspace version restamps without ignoring constraints."""

    def stamp(text: str, versions: set[str]) -> str:
        """Replace workspace version stamps without changing dependency constraints."""
        for version in sorted(versions, key=len, reverse=True):
            text = re.sub(r"(?<![\w.+-])" + re.escape(version) + r"(?![\w.+-])", "<workspace-version>", text)
        return text

    def normalize(item):
        """Normalize workspace dependency versions recursively for release comparison."""
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, str):
            match = re.match(r"([A-Za-z0-9_.-]+)(.*)", item)
            if match and match[1] in workspace_versions:
                return match[1] + stamp(match[2], workspace_versions[match[1]])
            return item
        if not isinstance(item, dict):
            return item
        result = {key: normalize(child) for key, child in item.items()}
        versions = workspace_versions.get(item.get("name"))
        if versions:
            if result.get("version") in versions:
                result["version"] = "<workspace-version>"
            if isinstance(result.get("specifier"), str):
                result["specifier"] = stamp(result["specifier"], versions)
        return result

    return normalize(value)


def validate_dependency_compatibility(commit: str, source_ref: str) -> None:
    """Bind qualification to every third-party resolution and runtime setting."""
    snapshots = []
    locks = [tomllib.loads(_run("git", "show", f"{ref}:uv.lock").decode()) for ref in (commit, source_ref)]
    versions: dict[str, set[str]] = {}
    for lock in locks:
        for package in lock["package"]:
            if any(key in package.get("source", {}) for key in ("editable", "virtual", "directory")):
                versions.setdefault(package["name"], set()).add(package["version"])
    for ref, lock in zip((commit, source_ref), locks, strict=True):
        snapshot = {"lock": normalize_dependencies(lock, versions)}
        for path in MANIFESTS:
            metadata = tomllib.loads(_run("git", "show", f"{ref}:{path}").decode())
            snapshot[path] = normalize_dependencies(
                {
                    "project": metadata.get("project", {}),
                    "dependency-groups": metadata.get("dependency-groups", {}),
                    "uv": metadata.get("tool", {}).get("uv", {}),
                    "build-system": metadata.get("build-system", {}),
                },
                versions,
            )
        snapshots.append(snapshot)
    _require(snapshots[0] == snapshots[1], "Qualification dependency graph changed. Qualify a new helper release.")


def check_release(*, kit: Path, trusted_root: Path, release_tag: str, source_ref: str, cosign: str) -> str:
    """Authenticate private evidence copies, then prove source compatibility."""
    import tempfile

    _require(trusted_root.is_absolute(), "The independently provisioned trust root must be absolute")
    _require(_object(_run(cosign, "version", "--json")).get("gitVersion") == "v3.1.3", "Unqualified cosign version")
    documents = {
        name: _read(kit / name)
        for name in (
            "helper-release.json",
            "helper-verification.sigstore.json",
            "helper-qualification.json",
            "helper-qualification.sigstore.json",
        )
    }
    root_bytes = _read(trusted_root)
    with tempfile.TemporaryDirectory(prefix="helper-release-proof-") as directory:
        private = Path(directory)
        for name, value in {**documents, "trusted-root.json": root_bytes}.items():
            (private / name).write_bytes(value)
        for manifest, bundle in (
            ("helper-release.json", "helper-verification.sigstore.json"),
            ("helper-qualification.json", "helper-qualification.sigstore.json"),
        ):
            _run(
                cosign,
                "verify-blob",
                "--bundle",
                str(private / bundle),
                "--trusted-root",
                str(private / "trusted-root.json"),
                "--certificate-identity-regexp",
                IDENTITY,
                "--certificate-oidc-issuer",
                "https://token.actions.githubusercontent.com",
                str(private / manifest),
            )
        commit = validate_documents(
            documents["helper-release.json"], documents["helper-qualification.json"], release_tag
        )
    # A prepared release commit can change version stamps. It may not change
    # the reader, protocol, native storage or qualification implementation.
    _run("git", "merge-base", "--is-ancestor", commit, source_ref)
    _run("git", "diff", "--quiet", commit, source_ref, "--", *HELPER_PATHS)
    validate_dependency_compatibility(commit, source_ref)
    return commit


def main() -> None:
    """Validate signed helper evidence against the requested release source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--trusted-root", required=True, type=Path)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--source-ref", default="HEAD")
    parser.add_argument("--cosign", default="cosign")
    args = parser.parse_args()
    commit = check_release(**vars(args))
    print(f"Verified signed, two-platform helper qualification for source {commit}.")


if __name__ == "__main__":
    main()
