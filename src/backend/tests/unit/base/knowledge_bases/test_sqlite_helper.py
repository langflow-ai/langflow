"""Tests of the application/helper trust boundary without a Chroma dependency."""

import asyncio
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest
from langflow.services.knowledge_base_storage import helper

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize(
    "value",
    [
        "",
        "latest",
        "image:1.5.9",
        "ghcr.io/langflow-ai/langflow-chroma-migration:1.13",
        "attacker.example/helper@sha256:" + "0" * 64,
    ],
)
async def test_missing_or_mutable_helper_never_launches(value, tmp_path, monkeypatch):
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", value)

    async def forbidden(*_args, **_kwargs):
        pytest.fail("Unverified artifact must never launch a process")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(helper.MigrationHelperError, match=r"signed 1\.13"):
        await helper.export_snapshot(
            tmp_path,
            tmp_path / "output",
            collection_name="source",
            source_id="id",
            source_fingerprint="0" * 64,
            model_fingerprint=None,
        )


def test_fixed_container_boundary_does_not_mount_or_forward_host_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-sentinel")
    args = helper.isolated_command("docker", "verified-image", tmp_path, "private-reader")
    assert "--network=none" in args
    assert "--read-only" in args
    assert "--cap-drop=ALL" in args
    assert "--security-opt=no-new-privileges=true" in args
    assert "--pull=never" in args
    assert "--env" not in args
    assert "--env-file" not in args
    assert args.count("--mount") == 1
    assert args[args.index("--mount") + 1].endswith(",target=/source,readonly,bind-recursive=disabled")
    assert "OPENAI_API_KEY" not in helper._client_environment()


def test_snapshot_rejects_links_before_any_native_reader(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "chroma.sqlite3").write_bytes(b"synthetic")
    (source / "link").symlink_to(tmp_path)
    with pytest.raises(helper.MigrationHelperError, match="link or special"):
        helper._validate_snapshot(source)


def test_snapshot_rejects_hard_links(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "chroma.sqlite3").write_bytes(b"synthetic")
    os.link(source / "chroma.sqlite3", source / "alias")
    with pytest.raises(helper.MigrationHelperError, match="hard links"):
        helper._validate_snapshot(source)


def test_snapshot_size_is_bounded_before_native_reader(tmp_path, monkeypatch):
    (tmp_path / "chroma.sqlite3").write_bytes(b"more than limit")
    monkeypatch.setattr(helper, "_MAX_SOURCE_BYTES", 1)
    with pytest.raises(helper.MigrationHelperError, match="8 GiB"):
        helper._validate_snapshot(tmp_path)


def test_native_inventory_must_match_snapshot_identity(tmp_path):
    request = {"source_id": "expected", "source_fingerprint": "0" * 64, "model_fingerprint": None}
    path = tmp_path / "export"
    path.write_text(
        json.dumps(
            {
                "type": "header",
                "protocol_version": 1,
                **request,
                "source_id": "wrong-source",
                "source_version": "chroma-rust-1.5.9",
                "count": 0,
                "dimensions": None,
                "metric": "l2",
            }
        )
        + "\n"
    )
    with pytest.raises(helper.MigrationHelperError, match="does not match"):
        helper._read_header(path, request)


async def test_cancellation_drains_file_worker_before_it_can_close(tmp_path):
    started = threading.Event()
    release = threading.Event()
    path = tmp_path / "output"

    def write():
        started.set()
        assert release.wait(5)
        path.write_bytes(b"complete")

    task = asyncio.create_task(helper._disk_call(write))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(b"complete").digest()


async def test_cancel_during_creation_never_starts_reader_and_waits_for_removal(tmp_path, monkeypatch):
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", image)
    monkeypatch.delenv("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE", raising=False)
    monkeypatch.setattr(helper.shutil, "which", lambda name: f"/trusted/{name}")
    source = tmp_path / "source"
    source.mkdir()
    (source / "chroma.sqlite3").write_bytes(b"fixture")
    creating = asyncio.Event()
    release = asyncio.Event()
    created = False
    removed = False

    async def command(*args, **_kwargs):
        nonlocal created
        if args[1] == "version":
            return json.dumps({"gitVersion": "v3.1.3"}).encode()
        if args[1] == "create":
            creating.set()
            await release.wait()
            created = True
        return b""

    async def remove(_docker, _name):
        nonlocal removed
        assert created, "Cleanup must not race a still-pending create operation"
        removed = True

    async def forbidden_start(*_args, **_kwargs):
        pytest.fail("A cancelled creation must never start native parsing")

    monkeypatch.setattr(helper, "_command", command)
    monkeypatch.setattr(helper, "_remove_container", remove)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden_start)
    task = asyncio.create_task(
        helper.export_snapshot(
            source,
            tmp_path / "export.jsonl",
            collection_name="fixture",
            source_id="source",
            source_fingerprint="0" * 64,
            model_fingerprint=None,
        )
    )
    await asyncio.wait_for(creating.wait(), 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert removed
    assert not (tmp_path / "export.jsonl").exists()


def test_source_hard_links_are_rejected_before_snapshot_copy(tmp_path):
    from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError, snapshot_source

    outside = tmp_path / "private-outside"
    outside.write_bytes(b"private-sentinel")
    source = tmp_path / "source"
    source.mkdir()
    os.link(outside, source / "chroma.sqlite3")
    with pytest.raises(MaintenanceRequiredError, match="hard link"):
        snapshot_source(source, tmp_path / "snapshot", "0" * 64)
    assert not (tmp_path / "snapshot").exists()


def release_manifest(image):
    return {
        "protocol_version": 1,
        "image": image,
        "reader": "chroma-rust-1.5.9",
        "security_disposition": "approved synthetic test disposition",
        "commit": "a" * 40,
        "platforms": {
            f"linux/{architecture}": {
                "image_id": "sha256:" + digest * 64,
                "content_sha256": "e" * 64,
                "archive": f"helper-image-linux-{architecture}.tar",
                "archive_sha256": "f" * 64,
            }
            for architecture, digest in (("amd64", "1"), ("arm64", "2"))
        },
    }


@pytest.mark.parametrize(
    ("architecture", "expected"), [("x86_64", "1"), ("AMD64", "1"), ("arm64", "2"), ("aarch64", "2")]
)
def test_offline_manifest_selects_only_qualified_content_id(architecture, expected, monkeypatch):
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    monkeypatch.setattr(helper.platform, "machine", lambda: architecture)
    assert helper._release_image_id(json.dumps(release_manifest(image)).encode(), image) == "sha256:" + expected * 64


@pytest.mark.parametrize(
    ("field", "value"), [("image", "different-release"), ("reader", "other-reader"), ("protocol_version", True)]
)
def test_offline_manifest_rejects_different_release_or_protocol(field, value):
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    manifest = release_manifest(image)
    manifest[field] = value
    with pytest.raises(helper.MigrationHelperError, match="does not match"):
        helper._release_image_id(json.dumps(manifest).encode(), image)


@pytest.mark.parametrize(
    ("field", "value"), [("image_id", "local:tag"), ("archive", "../../archive.tar"), ("archive_sha256", "bad")]
)
def test_offline_manifest_rejects_unsigned_tags_or_invalid_archive_identity(field, value):
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    manifest = release_manifest(image)
    manifest["platforms"]["linux/amd64"][field] = value
    with pytest.raises(helper.MigrationHelperError, match="does not match"):
        helper._release_image_id(json.dumps(manifest).encode(), image)


def test_offline_manifest_rejects_duplicate_json_keys():
    with pytest.raises(helper.MigrationHelperError, match="does not match"):
        helper._release_image_id(b'{"image":"first","image":"second"}', "second")


@pytest.mark.parametrize("version", ["v2.5.2", "v3.1.2", "v4.0.0", "", None])
async def test_unqualified_cosign_never_verifies_or_stages(version, monkeypatch):
    async def command(*args, **_kwargs):
        assert args == ("cosign", "version", "--json")
        return json.dumps({"gitVersion": version}).encode()

    monkeypatch.setattr(helper, "_command", command)
    with pytest.raises(helper.MigrationHelperError, match=r"qualified cosign v3\.1\.3"):
        await helper._stage_verified_helper("docker", "cosign", "test-image")


async def test_online_verifies_identity_before_pulling_digest(monkeypatch):
    monkeypatch.delenv("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE", raising=False)
    calls = []

    async def command(*args, **_kwargs):
        calls.append(args)
        return json.dumps({"gitVersion": "v3.1.3"}).encode() if args[1] == "version" else b""

    monkeypatch.setattr(helper, "_command", command)
    assert await helper._stage_verified_helper("docker", "cosign", "release-digest") == "release-digest"
    assert [call[1] for call in calls] == ["version", "verify", "pull"]
    assert "--certificate-identity" in calls[1]
    assert helper._IDENTITY in calls[1]
    assert "--bundle" not in calls[1]
    assert calls[2] == ("docker", "pull", "--quiet", "release-digest")


async def test_offline_verifies_private_manifest_copy_without_registry_or_tuf(tmp_path, monkeypatch):
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    manifest = tmp_path / "release.json"
    inspected = {
        "Id": "sha256:" + "9" * 64,
        "Config": {"Entrypoint": ["/reader"], "User": "65532:65532", "Env": ["PATH=/usr/bin"]},
        "RootFS": {"Type": "layers", "Layers": ["sha256:" + "3" * 64]},
        "Os": "linux",
        "Architecture": "amd64",
    }
    release = release_manifest(image)
    release["platforms"]["linux/amd64"]["content_sha256"] = helper.image_content_sha256(inspected)
    manifest.write_text(json.dumps(release))
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(b"synthetic bundle")
    root = tmp_path / "trusted-root.json"
    root.write_bytes(b"independently provisioned trust root")
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE", str(bundle))
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_MANIFEST", str(manifest))
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_TRUSTED_ROOT", str(root))
    monkeypatch.setattr(helper.platform, "machine", lambda: "x86_64")
    calls = []

    async def command(*args, **_kwargs):
        calls.append(args)
        if args[1] == "version":
            return b'{"gitVersion":"v3.1.3"}'
        if args[1] == "image":
            assert args == (
                "docker",
                "image",
                "inspect",
                "langflow-chroma-migration-offline:" + helper.image_content_sha256(inspected),
            )
            return json.dumps([inspected]).encode()
        assert args[1] == "verify-blob"
        assert "--certificate-identity" in args
        assert helper._IDENTITY in args
        assert "--offline" not in args
        private_manifest = Path(args[-1])
        assert private_manifest != manifest
        assert json.loads(private_manifest.read_bytes())["image"] == image
        assert Path(args[args.index("--bundle") + 1]).read_bytes() == bundle.read_bytes()
        assert Path(args[args.index("--trusted-root") + 1]).read_bytes() == root.read_bytes()
        # A modification to the original after verification cannot change the
        # selected content ID. Selection uses the same bytes cosign verified.
        manifest.write_text("changed after private copy")
        return b""

    monkeypatch.setattr(helper, "_command", command)
    assert await helper._stage_verified_helper("docker", "cosign", image) == inspected["Id"]
    assert [call[1] for call in calls] == ["version", "verify-blob", "image"]
    assert not Path(calls[1][-1]).exists()


async def test_offline_requires_explicit_independent_trust(tmp_path, monkeypatch):
    monkeypatch.delenv("LANGFLOW_KB_MIGRATION_HELPER_MANIFEST", raising=False)
    monkeypatch.delenv("LANGFLOW_KB_MIGRATION_HELPER_TRUSTED_ROOT", raising=False)
    with pytest.raises(helper.MigrationHelperError, match="independently trusted"):
        await helper._verified_offline_image("cosign", "image", str(tmp_path / "bundle"))


async def test_failed_offline_signature_never_selects_an_image(tmp_path, monkeypatch):
    for setting in ("MANIFEST", "BUNDLE", "TRUSTED_ROOT"):
        path = tmp_path / setting
        path.write_bytes(b"untrusted data")
        monkeypatch.setenv(f"LANGFLOW_KB_MIGRATION_HELPER_{setting}", str(path))

    async def command(*_args, **_kwargs):
        msg = "signature rejected"
        raise helper.MigrationHelperError(msg)

    monkeypatch.setattr(helper, "_command", command)
    with pytest.raises(helper.MigrationHelperError, match="signature rejected"):
        await helper._verified_offline_image("cosign", "image", str(tmp_path / "BUNDLE"))


def test_verification_material_rejects_links_and_oversized_files(tmp_path):
    path = tmp_path / "material"
    path.write_bytes(b"synthetic")
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    with pytest.raises(helper.MigrationHelperError, match="absolute regular"):
        helper._verification_file(alias)
    with pytest.raises(helper.MigrationHelperError, match="size limit"):
        helper._verification_file(path, limit=1)


@pytest.mark.skipif(os.name == "nt", reason="Windows uses controller-managed ACLs")
def test_trust_anchor_rejects_group_writable_file(tmp_path):
    path = tmp_path / "trusted-root.json"
    path.write_bytes(b"synthetic trust root")
    path.chmod(0o664)
    with pytest.raises(helper.MigrationHelperError, match="invalid"):
        helper._verification_file(path, trusted=True)


@pytest.mark.parametrize("changed", ["Config", "RootFS", "Architecture"])
async def test_offline_loaded_image_must_match_signed_execution_content(monkeypatch, changed):
    inspected = {
        "Id": "sha256:" + "9" * 64,
        "Config": {"Entrypoint": ["/reader"]},
        "RootFS": {"Type": "layers", "Layers": ["sha256:" + "3" * 64]},
        "Os": "linux",
        "Architecture": "amd64",
    }
    entry = {"content_sha256": helper.image_content_sha256(inspected)}
    inspected[changed] = {
        "Config": {"Entrypoint": ["/untrusted"]},
        "RootFS": {"Type": "layers", "Layers": ["sha256:" + "4" * 64]},
        "Architecture": "arm64",
    }[changed]

    async def command(*_args, **_kwargs):
        return json.dumps([inspected]).encode()

    monkeypatch.setattr(helper, "_command", command)
    with pytest.raises(helper.MigrationHelperError, match="signed execution content"):
        await helper._offline_local_image("docker", entry)


def test_image_content_binding_ignores_store_identity_and_includes_execution_fields():
    inspected = {
        "Id": "sha256:" + "1" * 64,
        "Config": {"Cmd": ["read"]},
        "RootFS": {"Type": "layers", "Layers": ["sha256:" + "3" * 64]},
        "Os": "linux",
        "Architecture": "amd64",
    }
    digest = helper.image_content_sha256(inspected)
    assert digest == helper.image_content_sha256({**inspected, "Id": "sha256:" + "2" * 64, "Variant": ""})
    assert digest != helper.image_content_sha256({**inspected, "Config": {"Cmd": ["write"]}})


async def test_offline_cleanup_resolves_verified_local_identity(monkeypatch):
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", image)
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE", "signed-bundle")
    monkeypatch.setattr(helper.shutil, "which", lambda command: command)
    calls = []

    async def version(_cosign):
        pass

    async def verify(*_args):
        return {"content_sha256": "e" * 64}

    async def resolve(_docker, entry):
        assert entry["content_sha256"] == "e" * 64
        return "sha256:" + "9" * 64

    async def command(*args, **_kwargs):
        calls.append(args)
        return b""

    monkeypatch.setattr(helper, "_check_cosign_version", version)
    monkeypatch.setattr(helper, "_verified_offline_image", verify)
    monkeypatch.setattr(helper, "_offline_local_image", resolve)
    monkeypatch.setattr(helper, "_command", command)
    await helper.cleanup_helper_artifact()
    assert calls == [("docker", "image", "rm", "sha256:" + "9" * 64)]
