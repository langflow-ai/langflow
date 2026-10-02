"""Offline kit qualification binds authenticated artifacts before Docker sees them."""

import base64
import copy
import importlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def kit(monkeypatch):
    root = Path(__file__).resolve().parents[6]
    monkeypatch.syspath_prepend(str(root / "tools" / "chroma_migration_helper"))
    return importlib.import_module("signed_kit")


@pytest.fixture
def release(kit):
    manifest = {
        "protocol_version": 1,
        "image": "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64,
        "reader": "chroma-rust-1.5.9",
        "security_disposition": "synthetic test disposition",
        "commit": "1" * 40,
        "platforms": {
            target: {
                "image_id": "sha256:" + digit * 64,
                "content_sha256": "e" * 64,
                "archive": f"helper-image-{target.replace('/', '-')}.tar",
                "archive_sha256": digit * 64,
            }
            for target, digit in (("linux/amd64", "2"), ("linux/arm64", "3"))
        },
    }
    payload = json.dumps(manifest).encode()
    results = [
        {
            "schema_version": 1,
            "artifact_type": "langflow-chroma-migration-platform-qualification",
            "helper_image": manifest["image"],
            "source_commit": manifest["commit"],
            "release_manifest_sha256": kit.sha256(payload),
            "qualification_profile": kit.PROFILE,
            "platform": target,
            "image_id": entry["image_id"],
            "content_sha256": "e" * 64,
            "archive_sha256": entry["archive_sha256"],
            "qualified": True,
        }
        for target, entry in manifest["platforms"].items()
    ]
    return payload, results


def test_attestation_binds_both_platforms_and_exact_manifest(kit, release):
    payload, results = release
    combined = kit.build_attestation(payload, results)
    assert set(combined["platforms"]) == {"linux/amd64", "linux/arm64"}
    assert combined["release_manifest_sha256"] == kit.sha256(payload)
    assert combined["source_commit"] == "1" * 40
    assert all(entry["qualified"] is True for entry in combined["platforms"].values())


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("source_commit", "f" * 40),
        ("helper_image", "unrelated-image"),
        ("release_manifest_sha256", "f" * 64),
        ("image_id", "sha256:" + "f" * 64),
        ("content_sha256", "f" * 64),
        ("archive_sha256", "f" * 64),
        ("qualification_profile", "unsigned-fixture"),
        ("qualified", False),
        ("qualified", 1),
        ("schema_version", True),
    ],
)
def test_attestation_rejects_mixed_or_incomplete_evidence(kit, release, key, value):
    payload, results = release
    results[0][key] = value
    with pytest.raises(ValueError, match="does not match"):
        kit.build_attestation(payload, results)


def test_attestation_requires_each_platform_exactly_once(kit, release):
    payload, results = release
    for incomplete in ([results[0]], [results[0], copy.deepcopy(results[0])], []):
        with pytest.raises(ValueError, match=r"does not match|Both supported"):
            kit.build_attestation(payload, incomplete)


def test_archive_is_copied_and_authenticated_before_loading(kit, tmp_path):
    source, private = tmp_path / "archive.tar", tmp_path / "verified.tar"
    source.write_bytes(b"trusted synthetic archive")
    kit.copy_verified_archive(source, private, kit.sha256(source.read_bytes()))
    source.write_bytes(b"changed after verification")
    assert private.read_bytes() == b"trusted synthetic archive"
    private.unlink()
    with pytest.raises(ValueError, match="signed checksum"):
        kit.copy_verified_archive(source, private, "0" * 64)
    assert not private.exists()


def test_archive_rejects_symlink(kit, tmp_path):
    source, link = tmp_path / "archive.tar", tmp_path / "link.tar"
    source.write_bytes(b"archive")
    link.symlink_to(source)
    with pytest.raises(OSError, match=r"symbolic links|Too many levels"):
        kit.copy_verified_archive(link, tmp_path / "verified.tar", kit.sha256(source.read_bytes()))


def test_archive_does_not_replace_existing_destination(kit, tmp_path):
    source, destination = tmp_path / "archive.tar", tmp_path / "existing.tar"
    source.write_bytes(b"new")
    destination.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        kit.copy_verified_archive(source, destination, kit.sha256(source.read_bytes()))
    assert destination.read_bytes() == b"keep"


def test_negative_signature_preserves_bundle_structure_but_changes_signature(kit):
    original = {"mediaType": "sigstore", "messageSignature": {"signature": base64.b64encode(b"signature").decode()}}
    changed = json.loads(kit.changed_signature(json.dumps(original).encode()))
    assert changed["mediaType"] == original["mediaType"]
    assert base64.b64decode(changed["messageSignature"]["signature"]) == b"rignature"


def test_signed_qualification_requires_network_namespace(kit, monkeypatch):
    monkeypatch.setattr(kit.platform, "system", lambda: "Linux")
    monkeypatch.setattr(kit.socket, "if_nameindex", lambda: [(1, "lo"), (2, "eth0")])
    with pytest.raises(ValueError, match="isolated Linux network namespace"):
        kit.require_network_isolation()
    monkeypatch.setattr(kit.socket, "if_nameindex", lambda: [(1, "lo")])
    kit.require_network_isolation()


@pytest.mark.parametrize("signature_valid", [False, True])
async def test_invalid_signature_or_archive_never_reaches_docker(kit, release, monkeypatch, tmp_path, signature_valid):
    payload, _results = release
    manifest, bundle, trust = (tmp_path / name for name in ("release.json", "bundle.json", "trusted-root.json"))
    manifest.write_bytes(payload)
    bundle.write_text(json.dumps({"messageSignature": {"signature": base64.b64encode(b"signature").decode()}}))
    trust.write_text("{}")
    archive = tmp_path / "helper-image-linux-amd64.tar"
    archive.write_bytes(b"wrong archive bytes")
    monkeypatch.setattr(kit.platform, "system", lambda: "Linux")
    monkeypatch.setattr(kit.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(kit.socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(kit.shutil, "which", lambda executable: f"/qualified/{executable}")
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", "previous-value")
    calls = []

    async def _qualified_cosign():
        return None

    async def verify(*_args):
        calls.append("verify")
        if not signature_valid or len(calls) > 1:
            msg = "signature rejected"
            raise kit.helper.MigrationHelperError(msg)
        return "sha256:" + "2" * 64

    def forbidden_docker(*_args, **_kwargs):
        pytest.fail("Invalid verification material must never reach Docker")

    monkeypatch.setattr(kit.helper, "_verified_offline_image", verify)
    monkeypatch.setattr(kit.helper, "_check_cosign_version", lambda _cosign: _qualified_cosign())
    monkeypatch.setattr(kit.subprocess, "run", forbidden_docker)
    monkeypatch.setattr(kit.subprocess, "check_output", forbidden_docker)
    error = ValueError if signature_valid else kit.helper.MigrationHelperError
    with pytest.raises(error, match=r"signed checksum|signature rejected"):
        await kit.qualify_kit(
            image=json.loads(payload)["image"], manifest=manifest, bundle=bundle, trusted_root=trust, archive=archive
        )
    assert kit.os.environ["LANGFLOW_KB_MIGRATION_HELPER_IMAGE"] == "previous-value"
