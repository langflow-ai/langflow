"""Qualify signed offline kits inside a network namespace, then bind both results.

The workflow obtains its TUF root independently before disabling networking.
This script never downloads trust material, pulls images, or rebuilds artifacts.
"""

# This standalone CI process operates on its own disposable Docker daemon.
# Private helpers are deliberately exercised as production qualification targets.
# ruff: noqa: ASYNC221, S603, SLF001
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import platform
import shutil
import socket
import stat
import subprocess
import tempfile
from pathlib import Path

from langflow.services.knowledge_base_storage import helper
from qualify import qualify

PROFILE = "offline-native-reader-v1"
PLATFORMS = {"linux/amd64", "linux/arm64"}
EXPECTED_RECORDS = 717


def sha256(payload: bytes) -> str:
    """Hash release evidence bytes for immutable artifact binding."""
    return hashlib.sha256(payload).hexdigest()


def copy_verified_archive(source: Path, destination: Path, expected: str) -> None:
    """Load only a private copy whose bytes match the signed manifest."""
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    digest = hashlib.sha256()
    created = False
    try:
        with os.fdopen(descriptor, "rb") as stream, destination.open("xb") as target:
            created = True
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                msg = "Helper archive must be a regular file"
                raise ValueError(msg)
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                target.write(chunk)
        if digest.hexdigest() != expected:
            msg = "Helper archive does not match its signed checksum"
            raise ValueError(msg)
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def changed_signature(payload: bytes) -> bytes:
    """Mutate a signature for the offline verifier's rejection test."""
    bundle = json.loads(payload)
    signature = bytearray(base64.b64decode(bundle["messageSignature"]["signature"], validate=True))
    if not signature:
        msg = "Signature bundle has no message signature"
        raise ValueError(msg)
    signature[0] ^= 1
    bundle["messageSignature"]["signature"] = base64.b64encode(signature).decode()
    return json.dumps(bundle).encode()


def require_network_isolation() -> None:
    """Reject qualification when the signed kit can reach an external network."""
    if platform.system() != "Linux" or any(name != "lo" for _, name in socket.if_nameindex()):
        msg = "Signed offline qualification must run in an isolated Linux network namespace"
        raise ValueError(msg)


async def qualify_kit(*, image: str, manifest: Path, bundle: Path, trusted_root: Path, archive: Path) -> dict:
    """Validate signed offline artifacts and exercise rejection before source access."""
    require_network_isolation()
    docker, cosign = shutil.which("docker"), shutil.which("cosign")
    if not docker or not cosign:
        msg = "Docker and the qualified cosign binary are required"
        raise ValueError(msg)
    if not helper._IMAGE.fullmatch(image):
        msg = "Qualification requires an immutable project helper image"
        raise ValueError(msg)
    manifest_bytes = helper._verification_file(manifest.resolve(), limit=helper._MAX_MANIFEST_BYTES)
    bundle_bytes = helper._verification_file(bundle.resolve())
    trust_bytes = helper._verification_file(trusted_root.resolve(), trusted=True)
    names = (
        "LANGFLOW_KB_MIGRATION_HELPER_IMAGE",
        "LANGFLOW_KB_MIGRATION_HELPER_MANIFEST",
        "LANGFLOW_KB_MIGRATION_HELPER_BUNDLE",
        "LANGFLOW_KB_MIGRATION_HELPER_TRUSTED_ROOT",
    )
    previous = {name: os.environ.get(name) for name in names}
    try:
        with tempfile.TemporaryDirectory(prefix="langflow-signed-kit-") as directory:
            private = Path(directory)
            for name, content in (
                ("release.json", manifest_bytes),
                ("bundle.json", bundle_bytes),
                ("trust.json", trust_bytes),
            ):
                (private / name).write_bytes(content)
            os.environ.update(
                dict(
                    zip(
                        names,
                        (
                            image,
                            str(private / "release.json"),
                            str(private / "bundle.json"),
                            str(private / "trust.json"),
                        ),
                        strict=True,
                    )
                )
            )
            # The real verifier authenticates bytes before JSON selects an archive.
            await helper._check_cosign_version(cosign)
            await helper._verified_offline_image(cosign, image, str(private / "bundle.json"))
            release = json.loads(manifest_bytes)
            architecture = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64", "amd64": "amd64"}[
                platform.machine().lower()
            ]
            target = f"linux/{architecture}"
            entry = release["platforms"][target]
            if archive.name != entry["archive"]:
                msg = "Archive selection does not match the signed platform"
                raise ValueError(msg)

            # Both negative checks must fail before any image load or reader.
            (private / "bundle.json").write_bytes(changed_signature(bundle_bytes))
            try:
                await helper._verified_offline_image(cosign, image, str(private / "bundle.json"))
            except helper.MigrationHelperError:
                pass
            else:
                msg = "Production verifier accepted a changed signature"
                raise AssertionError(msg)
            finally:
                (private / "bundle.json").write_bytes(bundle_bytes)
            (private / "tampered.tar").write_bytes(b"changed signed archive")
            try:
                copy_verified_archive(private / "tampered.tar", private / "rejected.tar", entry["archive_sha256"])
            except ValueError:
                pass
            else:
                msg = "Archive verification accepted changed bytes"
                raise AssertionError(msg)

            verified_archive = private / "image.tar"
            copy_verified_archive(archive, verified_archive, entry["archive_sha256"])
            subprocess.run([docker, "image", "load", "--input", str(verified_archive)], check=True, timeout=600)
            image_id = await helper._stage_verified_helper(docker, cosign, image)
            inspected = json.loads(subprocess.check_output([docker, "image", "inspect", image_id], timeout=30))[0]
            if inspected["Id"] != image_id or inspected["Os"] + "/" + inspected["Architecture"] != target:
                msg = "Loaded Docker content or platform differs from signed manifest"
                raise AssertionError(msg)
            proof = await qualify(image, signed=True)
            if proof["records"] != EXPECTED_RECORDS or not proof["hostile_embedding_configuration"]:
                msg = "Signed native reader qualification is incomplete"
                raise AssertionError(msg)
            return {
                "schema_version": 1,
                "artifact_type": "langflow-chroma-migration-platform-qualification",
                "helper_image": image,
                "source_commit": release["commit"],
                "release_manifest_sha256": sha256(manifest_bytes),
                "qualification_profile": PROFILE,
                "platform": target,
                "image_id": entry["image_id"],
                "content_sha256": helper.image_content_sha256(inspected),
                "archive_sha256": entry["archive_sha256"],
                "qualified": True,
            }
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def build_attestation(manifest_bytes: bytes, results: list[dict]) -> dict:
    """Bind the two successful jobs to exactly the signed release manifest."""
    release = json.loads(manifest_bytes)
    helper._release_image_id(manifest_bytes, release["image"])
    platforms = {}
    fields = {
        "schema_version",
        "artifact_type",
        "helper_image",
        "source_commit",
        "release_manifest_sha256",
        "qualification_profile",
        "platform",
        "image_id",
        "content_sha256",
        "archive_sha256",
        "qualified",
    }
    for result in results:
        target = result.get("platform")
        if (
            set(result) != fields
            or type(result["schema_version"]) is not int
            or result["schema_version"] != 1
            or result["artifact_type"] != "langflow-chroma-migration-platform-qualification"
            or result["helper_image"] != release["image"]
            or result["source_commit"] != release["commit"]
            or result["release_manifest_sha256"] != sha256(manifest_bytes)
            or result["qualification_profile"] != PROFILE
            or result["qualified"] is not True
            or target not in PLATFORMS
            or target in platforms
            or result["image_id"] != release["platforms"][target]["image_id"]
            or result["content_sha256"] != release["platforms"][target]["content_sha256"]
            or result["archive_sha256"] != release["platforms"][target]["archive_sha256"]
        ):
            msg = "Platform qualification does not match this signed release"
            raise ValueError(msg)
        platforms[target] = {key: result[key] for key in ("image_id", "content_sha256", "archive_sha256", "qualified")}
    if set(platforms) != PLATFORMS:
        msg = "Both supported platforms must pass signed offline qualification"
        raise ValueError(msg)
    return {
        "schema_version": 1,
        "artifact_type": "langflow-chroma-migration-qualification",
        "helper_image": release["image"],
        "source_commit": release["commit"],
        "release_manifest_sha256": sha256(manifest_bytes),
        "qualification_profile": PROFILE,
        "platforms": platforms,
    }


def main() -> None:
    """Run signed-kit qualification and emit the evidence bound to its release manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("qualify")
    run.add_argument("--image", required=True)
    for name in ("manifest", "bundle", "trusted-root", "archive", "output"):
        run.add_argument(f"--{name}", type=Path, required=True)
    combine = commands.add_parser("attest")
    combine.add_argument("--manifest", type=Path, required=True)
    combine.add_argument("--result", type=Path, action="append", required=True)
    combine.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "qualify":
        result = asyncio.run(
            qualify_kit(
                image=args.image,
                manifest=args.manifest,
                bundle=args.bundle,
                trusted_root=args.trusted_root,
                archive=args.archive,
            )
        )
    else:
        result = build_attestation(args.manifest.read_bytes(), [json.loads(path.read_bytes()) for path in args.result])
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
