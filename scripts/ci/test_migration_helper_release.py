"""Release proof must bind signatures, both images and the source being published."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.ci.check_migration_helper_release import (
    QualificationError,
    check_release,
    normalize_dependencies,
    validate_dependency_compatibility,
    validate_documents,
)


def evidence():
    commit = "a" * 40
    manifest = {
        "protocol_version": 1,
        "image": "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "b" * 64,
        "reader": "chroma-rust-1.5.9",
        "security_disposition": "approved-disposition-reference",
        "commit": commit,
        "platforms": {
            platform: {
                "image_id": "sha256:" + value * 64,
                "content_sha256": "e" * 64,
                "archive": f"helper-image-{platform.replace('/', '-')}.tar",
                "archive_sha256": "e" * 64,
            }
            for platform, value in (("linux/amd64", "c"), ("linux/arm64", "d"))
        },
    }
    manifest_bytes = json.dumps(manifest).encode()
    qualification = {
        "schema_version": 1,
        "artifact_type": "langflow-chroma-migration-qualification",
        "helper_image": manifest["image"],
        "source_commit": commit,
        "release_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "qualification_profile": "offline-native-reader-v1",
        "platforms": {
            platform: {
                "image_id": item["image_id"],
                "content_sha256": item["content_sha256"],
                "archive_sha256": item["archive_sha256"],
                "qualified": True,
            }
            for platform, item in manifest["platforms"].items()
        },
    }
    return manifest_bytes, qualification, f"helper-1.13-{commit}"


class ReleaseQualificationTests(unittest.TestCase):
    def test_complete_binding(self):
        manifest, qualification, tag = evidence()
        assert validate_documents(manifest, json.dumps(qualification).encode(), tag) == "a" * 40

    def test_changed_platform_or_missing_proof_rejected(self):
        for mutate in (
            lambda value: value["platforms"].pop("linux/arm64"),
            lambda value: value["platforms"]["linux/amd64"].update(qualified=False),
            lambda value: value["platforms"]["linux/amd64"].update(image_id="sha256:" + "f" * 64),
            lambda value: value["platforms"]["linux/arm64"].update(archive_sha256="f" * 64),
            lambda value: value.update(release_manifest_sha256="f" * 64),
            lambda value: value.update(source_commit="f" * 40),
        ):
            manifest, qualification, tag = evidence()
            mutate(qualification)
            with self.subTest(qualification=qualification), pytest.raises(QualificationError):
                validate_documents(manifest, json.dumps(qualification).encode(), tag)

    def test_mutated_manifest_wrong_tag_duplicate_fields_rejected(self):
        manifest, qualification, tag = evidence()
        for data, candidate_tag in (
            (manifest + b" ", tag),
            (manifest, "helper-1.13-" + "f" * 40),
            (manifest.replace(b'"protocol_version": 1', b'"protocol_version": 1, "protocol_version": 1'), tag),
        ):
            with self.subTest(data=data), pytest.raises(QualificationError):
                validate_documents(data, json.dumps(qualification).encode(), candidate_tag)

    def test_signature_failures_stop_before_source_check(self):
        for failure_index in (1, 2):
            with self.subTest(failure_index=failure_index), tempfile.TemporaryDirectory() as directory:
                kit = Path(directory)
                manifest, qualification, tag = evidence()
                (kit / "helper-release.json").write_bytes(manifest)
                (kit / "helper-qualification.json").write_text(json.dumps(qualification))
                for filename in (
                    "helper-verification.sigstore.json",
                    "helper-qualification.sigstore.json",
                    "root.json",
                ):
                    (kit / filename).write_text("{}")
                calls = []

                def run(*args, calls=calls, failure_index=failure_index):
                    calls.append(args)
                    if len(calls) == failure_index + 1:
                        raise subprocess.CalledProcessError(1, args)
                    return b'{"gitVersion":"v3.1.3"}' if args[1] == "version" else b""

                with (
                    patch("scripts.ci.check_migration_helper_release._run", side_effect=run),
                    pytest.raises(subprocess.CalledProcessError),
                ):
                    check_release(
                        kit=kit, trusted_root=kit / "root.json", release_tag=tag, source_ref="HEAD", cosign="cosign"
                    )
                assert not any(call[0] == "git" for call in calls)

    def test_source_checks_run_after_both_signatures(self):
        with tempfile.TemporaryDirectory() as directory:
            kit = Path(directory)
            manifest, qualification, tag = evidence()
            (kit / "helper-release.json").write_bytes(manifest)
            (kit / "helper-qualification.json").write_text(json.dumps(qualification))
            for filename in ("helper-verification.sigstore.json", "helper-qualification.sigstore.json", "root.json"):
                (kit / filename).write_text("{}")
            with (
                patch(
                    "scripts.ci.check_migration_helper_release._run",
                    side_effect=[b'{"gitVersion":"v3.1.3"}', b"", b"", b"", b""],
                ) as run,
                patch("scripts.ci.check_migration_helper_release.validate_dependency_compatibility") as dependencies,
            ):
                check_release(
                    kit=kit, trusted_root=kit / "root.json", release_tag=tag, source_ref="HEAD", cosign="cosign"
                )
            assert [call.args[1] for call in run.call_args_list] == [
                "version",
                "verify-blob",
                "verify-blob",
                "merge-base",
                "diff",
            ]
            dependencies.assert_called_once_with("a" * 40, "HEAD")

    def test_dependency_binding_allows_only_workspace_version_stamps(self):
        before = {"name": "lfx", "version": "1.13.0rc1", "dependencies": ["lfx==1.13.0rc1", "apsw==3.53.4.0"]}
        after = {"name": "lfx", "version": "1.13.0", "dependencies": ["lfx==1.13.0", "apsw==3.53.4.0"]}
        assert normalize_dependencies(before, {"lfx": {"1.13.0rc1", "1.13.0"}}) == normalize_dependencies(
            after, {"lfx": {"1.13.0rc1", "1.13.0"}}
        )
        for dependency in ("apsw==3.52.0.0", "lfx>=1.12.0"):
            changed = {**after, "dependencies": ["lfx==1.13.0", dependency]}
            assert normalize_dependencies(before, {"lfx": {"1.13.0rc1", "1.13.0"}}) != normalize_dependencies(
                changed, {"lfx": {"1.13.0rc1", "1.13.0"}}
            )

    def test_unchanged_constraints_survive_workspace_restamps(self):
        for before_version, after_version in (("1.13.0.dev0", "1.13.0"), ("1.13.0", "1.13.1")):
            with self.subTest(before=before_version, after=after_version):
                versions = {"lfx": {before_version, after_version}}
                before = {"name": "lfx", "version": before_version, "dependencies": ["lfx~=1.13.0"]}
                after = {**before, "version": after_version}
                assert normalize_dependencies(before, versions) == normalize_dependencies(after, versions)
                changed = {**after, "dependencies": ["lfx>=1.13.0"]}
                assert normalize_dependencies(before, versions) != normalize_dependencies(changed, versions)

    def test_changed_native_lock_rejected(self):
        lock = b'[[package]]\nname="apsw"\nversion="3.53.4.0"\nsource={registry="https://pypi.org/simple"}\n'
        metadata = b'[project]\nname="lfx"\nversion="1.13.0"\n'
        reads = [
            lock,
            lock.replace(b"3.53.4.0", b"3.52.0.0"),
            metadata,
            metadata,
            metadata,
            metadata,
            metadata,
            metadata,
        ]
        with (
            patch("scripts.ci.check_migration_helper_release._run", side_effect=reads),
            pytest.raises(QualificationError, match="dependency graph changed"),
        ):
            validate_dependency_compatibility("a" * 40, "HEAD")


if __name__ == "__main__":
    unittest.main()
