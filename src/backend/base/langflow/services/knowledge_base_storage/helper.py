"""Verified, network-isolated one-time legacy reader.

The application never installs or imports Chroma. Release engineering publishes
the separate signed OCI artifact. Managed upgrades stage its exact digest (or
load the offline kit) before entering maintenance. Missing prerequisites leave
legacy stores fenced and produce an actionable error, never an empty store.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import tempfile
from pathlib import Path
from uuid import uuid4

from lfx.base.knowledge_bases.migration.protocol import ExportHeader

_IMAGE = re.compile(r"ghcr\.io/langflow-ai/langflow-chroma-migration@sha256:[a-f0-9]{64}\Z")
_IDENTITY = (
    "https://github.com/langflow-ai/langflow/.github/workflows/chroma-migration-helper.yml@refs/heads/release-1.13.0"
)
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_MAX_OUTPUT_BYTES = 64 * 1024**3
_TIMEOUT_SECONDS = 3600
_MAX_SOURCE_BYTES = 8 * 1024**3
_MAX_SOURCE_FILES = 100_000
_MAX_HEADER_BYTES = 16_384
_MAX_ID_BYTES = 4096
_COSIGN_VERSION = "v3.1.3"
_MAX_VERIFICATION_FILE_BYTES = 1024 * 1024
_MAX_MANIFEST_BYTES = 16_384


class MigrationHelperError(RuntimeError):
    """Safe operator-facing helper failure without source or credential text."""


async def _disk_call(function, *args):
    """Cancellation must not close a file while its worker is still writing."""
    return await _drain_task(asyncio.create_task(asyncio.to_thread(function, *args)))


async def _drain_task(task):
    """Finish a bounded owned operation before propagating any cancellation."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            if not cancelled:
                raise
    if cancelled:
        task.exception()
        raise asyncio.CancelledError
    return task.result()


async def _stop_reader(docker, name, process):
    # Creation has finished before execution begins. Stop/drain the attach
    # client, then remove the known container. A late create cannot race this.
    """Stop the isolated export reader and drain its subprocess handles."""
    if process is not None and process.returncode is None:
        process.kill()
        await process.wait()
    await _remove_container(docker, name)


def _client_environment() -> dict[str, str]:
    # Docker/cosign need the controller's registry configuration. These values
    # are never passed into the container. No model/database credentials pass
    # through to either client.
    """Build a restricted subprocess environment for helper verification and execution."""
    names = (
        "PATH",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "HOME",
        "SYSTEMROOT",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CONFIG",
        "DOCKER_CERT_PATH",
        "DOCKER_TLS_VERIFY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    )
    return {name: os.environ[name] for name in names if name in os.environ}


async def _command(*args: str, timeout: int = 120, capture: bool = False) -> bytes:
    """Run a bounded helper command and drain its process on failure or cancellation."""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=_client_environment(),
        )
    except OSError as exc:
        msg = "The signed migration helper requires Docker and cosign on the upgrade controller."
        raise MigrationHelperError(msg) from exc

    async def complete() -> bytes:
        """Collect bounded verification output and require a successful process exit."""
        output = bytearray()
        if capture and process.stdout is not None:
            while chunk := await process.stdout.read(_MAX_HEADER_BYTES + 1):
                output.extend(chunk)
                if len(output) > _MAX_HEADER_BYTES:
                    msg = "The verification client returned an oversized response."
                    raise MigrationHelperError(msg)
        await process.wait()
        return bytes(output)

    try:
        output = await asyncio.wait_for(complete(), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        task = asyncio.create_task(process.wait())
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        raise
    if process.returncode:
        msg = "Helper verification or staging failed. Check the signed release artifact and controller runtime."
        raise MigrationHelperError(msg)
    return output


def _verification_file(path: Path, *, limit: int = _MAX_VERIFICATION_FILE_BYTES, trusted: bool = False) -> bytes:
    """Read bounded local verification material before making a private copy."""
    if not path.is_absolute() or path.is_symlink():
        msg = "Helper verification files must be absolute regular files."
        raise MigrationHelperError(msg)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValueError
            if trusted and os.name != "nt" and (info.st_uid not in (0, os.getuid()) or info.st_mode & 0o022):
                raise ValueError
            result = stream.read(limit + 1)
            if len(result) > limit:
                raise ValueError
            return result
    except (OSError, ValueError) as exc:
        msg = "Helper verification files are missing, invalid, or exceed their size limit."
        raise MigrationHelperError(msg) from exc


def _release_platform(payload: bytes, image: str) -> dict[str, str]:
    """Bind a signed manifest to the requested release and local platform."""

    def unique_pairs(pairs):
        """Decode helper evidence only when every JSON key is unique."""
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        manifest = json.loads(payload, object_pairs_hook=unique_pairs)
        if (
            type(manifest) is not dict
            or set(manifest) != {"protocol_version", "image", "reader", "security_disposition", "commit", "platforms"}
            or type(manifest["protocol_version"]) is not int
            or manifest["protocol_version"] != 1
            or manifest["image"] != image
            or manifest["reader"] != "chroma-rust-1.5.9"
            or not isinstance(manifest["security_disposition"], str)
            or not manifest["security_disposition"].strip()
            or not isinstance(manifest["commit"], str)
            or not re.fullmatch(r"[a-f0-9]{40}", manifest["commit"])
        ):
            raise ValueError
        platforms = manifest["platforms"]
        if type(platforms) is not dict or set(platforms) != {"linux/amd64", "linux/arm64"}:
            raise ValueError
        for target, entry in platforms.items():
            if (
                type(entry) is not dict
                or set(entry) != {"image_id", "content_sha256", "archive", "archive_sha256"}
                or not isinstance(entry["image_id"], str)
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", entry["image_id"])
                or not isinstance(entry["content_sha256"], str)
                or not _SHA256.fullmatch(entry["content_sha256"])
                or entry["archive"] != f"helper-image-{target.replace('/', '-')}.tar"
                or not isinstance(entry["archive_sha256"], str)
                or not _SHA256.fullmatch(entry["archive_sha256"])
            ):
                raise ValueError
        architecture = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}[
            platform.machine().lower()
        ]
        return platforms[f"linux/{architecture}"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        msg = "The signed helper manifest does not match this release or supported controller platform."
        raise MigrationHelperError(msg) from exc


async def _check_cosign_version(cosign: str) -> None:
    """Reject an unqualified cosign version before helper verification."""
    try:
        version = json.loads(await _command(cosign, "version", "--json", capture=True))
        if version.get("gitVersion") != _COSIGN_VERSION:
            raise ValueError
    except (AttributeError, TypeError, ValueError) as exc:
        msg = f"The migration controller requires the qualified cosign {_COSIGN_VERSION} release."
        raise MigrationHelperError(msg) from exc


async def _verified_offline_image(cosign: str, image: str, bundle: str) -> dict[str, str]:
    """Verify a signed content-ID manifest without registry or TUF requests.

    The controller provisions Sigstore's trusted root through authenticated TUF
    before entering the air gap. A root supplied by an untrusted kit is not a
    trust anchor. Cosign receives only private copies so verification and later
    interpretation cannot observe different manifest contents.
    """
    manifest = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_MANIFEST", "")
    trusted_root = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_TRUSTED_ROOT", "")
    if not manifest or not trusted_root:
        msg = "Offline migration requires the signed helper manifest, bundle, and independently trusted Sigstore root."
        raise MigrationHelperError(msg)
    manifest_bytes = await _disk_call(_verification_file, Path(manifest))
    if len(manifest_bytes) > _MAX_MANIFEST_BYTES:
        msg = "The helper release manifest exceeds its size limit."
        raise MigrationHelperError(msg)
    bundle_bytes = await _disk_call(_verification_file, Path(bundle))
    trusted_root_bytes = await _disk_call(lambda: _verification_file(Path(trusted_root), trusted=True))
    with tempfile.TemporaryDirectory(prefix="langflow-helper-verification-") as directory:
        private = Path(directory)
        for name, content in (
            ("release.json", manifest_bytes),
            ("bundle.json", bundle_bytes),
            ("trusted-root.json", trusted_root_bytes),
        ):
            (private / name).write_bytes(content)
        await _command(
            cosign,
            "verify-blob",
            "--bundle",
            str(private / "bundle.json"),
            "--trusted-root",
            str(private / "trusted-root.json"),
            "--certificate-identity",
            _IDENTITY,
            "--certificate-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            str(private / "release.json"),
        )
    return _release_platform(manifest_bytes, image)


def _release_image_id(payload: bytes, image: str) -> str:
    """Read the publisher's ID for release qualification evidence."""
    return _release_platform(payload, image)["image_id"]


def image_content_sha256(inspected: dict) -> str:
    """Bind executable configuration and verified uncompressed filesystem layers.

    Docker's classic store IDs hash the config while its containerd store IDs
    hash manifests. These execution fields survive save/load on either store.
    Inspect a loaded signed archive, authenticate these fields, and execute only
    the returned immutable local ID. Never execute the archive's mutable tag.
    """
    try:
        fields = {key: inspected[key] for key in ("Config", "RootFS", "Os", "Architecture")}
        fields["Variant"] = inspected.get("Variant") or ""
        if (
            not isinstance(fields["Config"], dict)
            or not isinstance(fields["RootFS"], dict)
            or fields["RootFS"].get("Type") != "layers"
            or not isinstance(fields["RootFS"].get("Layers"), list)
            or not fields["RootFS"]["Layers"]
            or any(
                not isinstance(layer, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", layer)
                for layer in fields["RootFS"]["Layers"]
            )
            or fields["Os"] != "linux"
            or fields["Architecture"] not in ("amd64", "arm64")
            or not isinstance(fields["Variant"], str)
        ):
            raise ValueError
        return hashlib.sha256(
            json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        ).hexdigest()
    except (KeyError, TypeError, ValueError) as exc:
        msg = "The loaded helper image has invalid execution content."
        raise MigrationHelperError(msg) from exc


async def _offline_local_image(docker: str, entry: dict[str, str]) -> str:
    """Authenticate a loaded offline image before selecting its local immutable ID."""
    reference = "langflow-chroma-migration-offline:" + entry["content_sha256"]
    try:
        inspected = json.loads(await _command(docker, "image", "inspect", reference, capture=True))[0]
        local_id = inspected["Id"]
        if (
            not isinstance(local_id, str)
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", local_id)
            or image_content_sha256(inspected) != entry["content_sha256"]
        ):
            raise ValueError
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        msg = "The loaded offline helper does not match the signed execution content."
        raise MigrationHelperError(msg) from exc
    return local_id


async def _stage_verified_helper(docker: str, cosign: str, image: str) -> str:
    """Verify the configured helper and stage its immutable image identity."""
    await _check_cosign_version(cosign)
    bundle = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE")
    if bundle:
        entry = await _verified_offline_image(cosign, image, bundle)
        return await _offline_local_image(docker, entry)
    await _command(
        cosign,
        "verify",
        "--certificate-identity",
        _IDENTITY,
        "--certificate-oidc-issuer",
        "https://token.actions.githubusercontent.com",
        image,
    )
    await _command(docker, "pull", "--quiet", image, timeout=600)
    return image


async def _remove_container(docker: str, name: str) -> None:
    """A missing --rm container is success, an unreachable daemon is not."""
    try:
        await _command(docker, "rm", "--force", name, timeout=60)
    except MigrationHelperError:
        process = await asyncio.create_subprocess_exec(
            docker,
            "container",
            "ls",
            "--all",
            "--filter",
            f"name=^/{name}$",
            "--format",
            "{{.Names}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
            env=_client_environment(),
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 30)
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode or output.strip():
            msg = "Helper cleanup could not be confirmed. Check the upgrade controller's Docker daemon."
            raise MigrationHelperError(msg) from None


async def cleanup_helper_artifact() -> None:
    """Remove only the dedicated helper image, without forcing active readers.

    Call after the controller's migration batch has finished. A failure is a
    separate cleanup condition, not permission to roll routing back to Chroma.
    """
    image = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", "")
    docker = shutil.which("docker")
    if _IMAGE.fullmatch(image) and docker:
        bundle = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE")
        if bundle:
            cosign = shutil.which("cosign")
            if not cosign:
                msg = "Offline helper cleanup requires its verified release manifest and cosign."
                raise MigrationHelperError(msg)
            await _check_cosign_version(cosign)
            entry = await _verified_offline_image(cosign, image, bundle)
            image = await _offline_local_image(docker, entry)
        await _command(docker, "image", "rm", image, timeout=60)


def _validate_snapshot(snapshot: Path) -> Path:
    """Reject unsafe snapshot paths before mounting legacy data into the reader."""
    if not snapshot.is_absolute() or snapshot.is_symlink() or not snapshot.is_dir():
        msg = "Migration snapshot must be a private absolute directory."
        raise MigrationHelperError(msg)
    snapshot = snapshot.resolve(strict=True)
    # --mount uses a comma-separated grammar, not shell quoting.
    if "," in str(snapshot) or "\n" in str(snapshot) or "\r" in str(snapshot):
        msg = "Migration snapshot path cannot be represented by the isolation runtime."
        raise MigrationHelperError(msg)
    count = 0
    size = 0
    for current, directories, files in os.walk(snapshot, followlinks=False):
        for name in (*directories, *files):
            info = (Path(current) / name).lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                msg = "Migration snapshot contains a link or special file."
                raise MigrationHelperError(msg)
            if stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    msg = "Migration snapshot contains hard links."
                    raise MigrationHelperError(msg)
                size += info.st_size
                count += 1
                if size > _MAX_SOURCE_BYTES or count > _MAX_SOURCE_FILES:
                    msg = "Source exceeds this helper's qualified 8 GiB or file-count limit."
                    raise MigrationHelperError(msg)
    if not (snapshot / "chroma.sqlite3").is_file():
        msg = "Migration snapshot has no source database."
        raise MigrationHelperError(msg)
    return snapshot


def isolated_command(docker: str, image: str, snapshot: Path, name: str) -> list[str]:
    """Fixed isolation profile. There is no arbitrary command or mount input."""
    uid = os.getuid() if hasattr(os, "getuid") else 10001
    # Never use uid zero, even when the app itself is run as root. A root
    # controller must stage a readable snapshot for the helper uid explicitly.
    uid = uid or 10001
    return [
        docker,
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "--interactive",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--user",
        str(uid),
        "--pids-limit=128",
        f"--cpus={min(2, os.cpu_count() or 1)}",
        "--memory=16g",
        "--memory-swap=16g",
        "--ulimit",
        "nofile=1024:1024",
        "--ulimit",
        "core=0:0",
        "--log-driver=none",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=268435456,mode=1777",  # noqa: S108 -- private container tmpfs
        "--tmpfs",
        "/work:rw,noexec,nosuid,nodev,size=10737418240,mode=1777",
        "--mount",
        f"type=bind,source={snapshot},target=/source,readonly,bind-recursive=disabled",
        image,
    ]


def _read_header(path: Path, request: dict) -> ExportHeader:
    """Decode and validate the helper header against the migration request."""
    with path.open("rb") as stream:
        line = stream.readline(_MAX_HEADER_BYTES + 1)
    if len(line) > _MAX_HEADER_BYTES or not line.endswith(b"\n"):
        msg = "Migration helper returned an invalid inventory header."
        raise MigrationHelperError(msg)
    try:
        data = json.loads(line)
        if type(data) is not dict or data.pop("type") != "header" or data.pop("protocol_version") != 1:
            raise ValueError
        header = ExportHeader(**data)
        if (
            header.source_id != request["source_id"]
            or header.source_fingerprint != request["source_fingerprint"]
            or header.model_fingerprint != request["model_fingerprint"]
            or header.source_version != "chroma-rust-1.5.9"
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        msg = "Migration helper inventory does not match the requested snapshot."
        raise MigrationHelperError(msg) from exc
    return header


async def export_snapshot(
    snapshot_path: Path,
    output_path: Path,
    *,
    collection_name: str,
    source_id: str,
    source_fingerprint: str,
    model_fingerprint: str | None,
) -> ExportHeader:
    """Export a stopped snapshot and return successful native source inventory.

    This is not qualification. The coordinator must call ``qualify_export``
    against this header and verify destination rows before activating routing.
    Cancellation stops the container and waits for cleanup before returning.
    """
    image = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", "")
    if not _IMAGE.fullmatch(image):
        msg = "Stage the signed 1.13 migration helper and set LANGFLOW_KB_MIGRATION_HELPER_IMAGE to its release digest."
        raise MigrationHelperError(msg)
    if not _SHA256.fullmatch(source_fingerprint) or (
        model_fingerprint is not None and not _SHA256.fullmatch(model_fingerprint)
    ):
        msg = "Migration source/model fingerprint is invalid."
        raise MigrationHelperError(msg)
    if (
        not collection_name
        or not source_id
        or len(collection_name.encode()) > _MAX_ID_BYTES
        or len(source_id.encode()) > _MAX_ID_BYTES
    ):
        msg = "Migration source identity is invalid."
        raise MigrationHelperError(msg)
    snapshot = await asyncio.to_thread(_validate_snapshot, snapshot_path)
    if not output_path.is_absolute() or output_path.is_symlink() or output_path.exists():
        msg = "Migration output must be a new private absolute file."
        raise MigrationHelperError(msg)
    docker = shutil.which("docker")
    cosign = shutil.which("cosign")
    if not docker or not cosign:
        msg = "The upgrade controller requires Docker and cosign. The application installs neither."
        raise MigrationHelperError(msg)
    # Online staging selects the signed OCI digest. Offline staging selects
    # only the image content ID in its independently verified release manifest.
    image = await _stage_verified_helper(docker, cosign, image)
    name = f"langflow-kb-migration-{uuid4().hex}"
    partial = output_path.with_name(f".{output_path.name}.{uuid4().hex}.partial")
    request = {
        "collection_name": collection_name,
        "source_id": source_id,
        "source_fingerprint": source_fingerprint,
        "model_fingerprint": model_fingerprint,
    }
    process = None
    creation_started = False
    cleaned = False
    try:
        create = isolated_command(docker, image, snapshot, name)
        create[1] = "create"
        create.remove("--rm")
        creation_started = True
        # Cancellation waits for creation to finish, then removes this known,
        # still-unstarted container. Native parsing cannot start in this phase.
        await _drain_task(asyncio.create_task(_command(*create)))
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            process = await asyncio.create_subprocess_exec(
                docker,
                "start",
                "--attach",
                "--interactive",
                name,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=_client_environment(),
            )

            async def transfer() -> None:
                """Send the export request and stream validated helper output to the target."""
                if process is None or process.stdin is None or process.stdout is None:
                    msg = "Migration helper pipes could not be opened."
                    raise MigrationHelperError(msg)
                process.stdin.write(json.dumps(request, separators=(",", ":")).encode())
                await process.stdin.drain()
                process.stdin.close()
                total = 0
                while chunk := await process.stdout.read(256 * 1024):
                    total += len(chunk)
                    if total > _MAX_OUTPUT_BYTES:
                        msg = "Migration export exceeds the qualified output limit."
                        raise MigrationHelperError(msg)
                    await _disk_call(stream.write, chunk)
                await process.wait()
                if process.returncode:
                    msg = "Legacy reader failed. Snapshot retained. Check source format, capacity and helper isolation."
                    raise MigrationHelperError(msg)
                await _disk_call(stream.flush)
                await _disk_call(os.fsync, stream.fileno())

            await asyncio.wait_for(transfer(), _TIMEOUT_SECONDS)
        header = await _disk_call(_read_header, partial, request)
        await _drain_task(asyncio.create_task(_stop_reader(docker, name, process)))
        cleaned = True
        partial.replace(output_path)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        msg = "Migration helper exceeded its time limit. Snapshot is retained."
        raise MigrationHelperError(msg) from exc
    finally:
        try:
            if creation_started and not cleaned:
                await _drain_task(asyncio.create_task(_stop_reader(docker, name, process)))
        finally:
            partial.unlink(missing_ok=True)
    return header
