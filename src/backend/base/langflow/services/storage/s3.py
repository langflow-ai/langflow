"""S3-based storage service implementation using aiobotocore.

This service handles file storage operations with AWS S3, including
file upload, download, deletion, and listing operations.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import os
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from langflow.logging.logger import logger

from .service import StorageReadiness, StorageService, _refuse_bad_move, validate_namespace

# S3 parts are 5 MiB at least, except the last one.
STREAM_PART_SIZE = 8 * 1024 * 1024
# How long an upload link stays good for. Long enough for one large file over a slow link,
# short enough that a leaked URL is not a standing write. The caller can ask for less.
UPLOAD_LINK_TTL = 3600
# Server-side encryption modes whose ETag is not the body's MD5.
_ETAG_NOT_MD5_ENCRYPTION = {"aws:kms", "aws:kms:dsse"}
# User metadata key (``x-amz-meta-md5``) holding the body's MD5, written with every object this
# service stores, so the checksum is known even where the ETag is not one.
MD5_METADATA_KEY = "md5"
_MD5_PATTERN = re.compile(r"[0-9a-f]{32}")


def _md5_hex(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def md5_from_head(head: dict[str, Any]) -> str | None:
    """The body's MD5 from a HeadObject response: the ETag when it is one, else the stored label.

    S3 sets the ETag to the MD5 of the body only for a single-part upload stored in
    plain or SSE-S3 form. A multipart ETag carries a ``-``, and objects under SSE-KMS or
    customer-provided keys (SSE-C) get an ETag that is not an MD5 at all. For those the
    ``md5`` metadata this service writes answers instead. The ETag wins when both exist,
    since S3 computes it and a label is only what the writer said. Any rewrite of the
    object that does not carry the label drops it, so a stale label cannot outlive its body.
    """
    etag = head.get("ETag", "").strip('"')
    encrypted = head.get("ServerSideEncryption") in _ETAG_NOT_MD5_ENCRYPTION or head.get("SSECustomerAlgorithm")
    if etag and "-" not in etag and not encrypted:
        return etag
    label = (head.get("Metadata") or {}).get(MD5_METADATA_KEY, "").lower()
    return label if _MD5_PATTERN.fullmatch(label) else None


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService


class S3StorageService(StorageService):
    """A service class for handling S3 storage operations using aiobotocore."""

    def __init__(self, session_service: SessionService, settings_service: SettingsService) -> None:
        """Initialize the S3 storage service with session and settings services.

        Args:
            session_service: The session service instance
            settings_service: The settings service instance

        Raises:
            ImportError: If aiobotocore is not installed
            ValueError: If required S3 configuration is missing
        """
        super().__init__(session_service, settings_service)

        # Validate required S3 configuration
        self.bucket_name = settings_service.settings.object_storage_bucket_name
        if not self.bucket_name:
            msg = "S3 bucket name is required when using S3 storage"
            raise ValueError(msg)

        self.prefix = settings_service.settings.object_storage_prefix or ""
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        self.tags = settings_service.settings.object_storage_tags or {}

        try:
            from aiobotocore.session import get_session
        except ImportError as exc:
            msg = "aiobotocore is required for S3 storage. Install it with: uv pip install aiobotocore"
            raise ImportError(msg) from exc

        # Create session - AWS credentials are picked up from environment variables
        self.session = get_session()
        # One client per event loop. A client is bound to the loop that made it, and
        # the service is reached from more than one: components running a loop of
        # their own, CLI paths behind asyncio.run.
        self._clients: dict[asyncio.AbstractEventLoop, tuple[AsyncGenerator[Any, None], Any]] = {}
        # Bumped by teardown, so a client still being built when it runs is not cached.
        self._generation = 0

        self.set_ready()
        logger.info(
            f"S3 storage initialized: bucket={self.bucket_name}, prefix={self.prefix}, "
            f"region={os.getenv('AWS_DEFAULT_REGION', 'default')}"
        )

    def _validate_identifiers(self, flow_id: str, file_name: str | None = None) -> None:
        """Reject flow_id / file_name values that could escape the flow namespace.

        Defense in depth at the S3 backend for GHSA-rcjh-r59h-gq37: the public-flow
        boundary in chat.py is the primary gate, but any caller reaching this
        backend with untrusted identifiers must still fail safely. Validation is
        synchronous and runs before any AWS call so a malformed input cannot be
        turned into a get_object on an arbitrary bucket key.
        """
        if (
            not isinstance(flow_id, str)
            or not flow_id
            or "/" in flow_id
            or "\\" in flow_id
            or ".." in flow_id
            or "\x00" in flow_id
        ):
            logger.error("Invalid flow_id contains path separators or traversal sequences")
            msg = "Invalid flow_id: contains path separators"
            raise ValueError(msg)

        if file_name is not None and (
            not isinstance(file_name, str)
            or not file_name
            or "/" in file_name
            or "\\" in file_name
            or ".." in file_name
            or "\x00" in file_name
        ):
            logger.error("Invalid file_name contains path separators or traversal sequences")
            msg = "Invalid file name: contains path separators"
            raise ValueError(msg)

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full S3 key for a file.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            str: The full S3 key (e.g., 'files/flow_123/myfile.txt')

        Raises:
            ValueError: If either identifier carries separators or traversal sequences.
        """
        # Defense in depth: every file operation validates its own identifiers, but this is a
        # public key builder whose result is also handed to callers directly (component path
        # resolution). Path shape must never be treated as authorization, so reject anything
        # that could compose a key outside the ``flow_id`` namespace. ``file_name`` is empty
        # when building a listing prefix (see ``list_files``), which stays allowed.
        self._validate_identifiers(flow_id, file_name or None)
        # note: prefix already contains the / at the end
        return f"{self.prefix}{flow_id}/{file_name}"

    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full S3 path to extract flow_id and file_name.

        Args:
            full_path: S3 path, may or may not include prefix
                e.g., "files/user_123/image.png" or "user_123/image.png"

        Returns:
            tuple[str, str]: A tuple of (flow_id, file_name)

        Examples:
            >>> parse_file_path("files/user_123/image.png")  # with prefix
            ("user_123", "image.png")
            >>> parse_file_path("user_123/image.png")  # without prefix
            ("user_123", "image.png")
        """
        # Remove prefix if present (but don't require it)
        path_without_prefix = full_path
        if self.prefix and full_path.startswith(self.prefix):
            path_without_prefix = full_path[len(self.prefix) :]

        # Split from the right to get the filename
        # Everything before the last "/" is the flow_id
        if "/" not in path_without_prefix:
            return "", path_without_prefix

        # Use rsplit to split from the right, limiting to 1 split
        flow_id, file_name = path_without_prefix.rsplit("/", 1)
        return flow_id, file_name

    def resolve_component_path(self, logical_path: str) -> str:
        """Return logical path as-is for S3 storage.

        For S3, components work with logical paths (flow_id/filename) and the
        storage service adds the prefix internally when performing operations.

        Args:
            logical_path: Path in format "flow_id/filename"

        Returns:
            str: The same logical path (components use this with storage service)
        """
        return logical_path

    async def _hold_client(self) -> AsyncGenerator[Any, None]:
        """Open a client and keep it open until this generator is closed.

        Holding the client in an async generator ties it to its loop: a loop that shuts
        down cleanly (``asyncio.run`` does) closes the async generators still open on
        it, so a client built on a loop of its own is closed there, on that loop.
        """
        async with self.session.create_client("s3") as client:
            yield client

    @contextlib.asynccontextmanager
    async def _get_client(self, *, shared: bool = True) -> AsyncIterator[Any]:
        """Yield this event loop's S3 client, building it on first use.

        Building a client per call costs a client and a TLS handshake for every
        operation. The client stays open until ``teardown`` or until its loop shuts
        down, so leaving the block does not close it.

        ``shared=False`` yields a client of its own, closed when the block exits.
        """
        if not shared:
            async with self.session.create_client("s3") as client:
                yield client
            return

        loop = asyncio.get_running_loop()
        # Its loop already closed what it could; only the reference is left to drop.
        # A loop closed without shutdown_asyncgens never closed its client; the GC has to.
        # Other threads prune and add entries too, so iterate a copy and tolerate a miss.
        for closed in [other for other in list(self._clients) if other.is_closed()]:
            self._clients.pop(closed, None)
        if (held := self._clients.get(loop)) is not None:
            yield held[1]
            return

        generation = self._generation
        holder = self._hold_client()
        client = await anext(holder)
        if generation != self._generation or loop in self._clients:
            # A teardown ran while this client was built, or another coroutine on this
            # loop built one first. Use it for this call only.
            try:
                yield client
            finally:
                await holder.aclose()
            return
        self._clients[loop] = (holder, client)
        yield client

    async def check_readiness(self) -> StorageReadiness:
        """Verify S3 credentials resolve and the configured bucket is reachable.

        Used by the production preflight. Resolves AWS credentials from the
        environment/instance role, then issues a ``head_bucket`` to confirm the
        bucket exists and is accessible. Distinguishes missing credentials,
        missing bucket, access denied, and general unreachability.
        """
        # Resolve credentials before any network call so "no creds" is reported
        # distinctly from "bucket unreachable". A misconfigured AWS profile/config
        # surfaces here too and is treated as a credentials failure.
        try:
            credentials = await self.session.get_credentials()
        except Exception as exc:  # noqa: BLE001 — botocore config errors (e.g. ProfileNotFound)
            return StorageReadiness(
                ok=False,
                backend="s3",
                detail=f"could not resolve AWS credentials: {exc}",
                reason="no-credentials",
            )
        if credentials is None:
            return StorageReadiness(
                ok=False,
                backend="s3",
                detail="no AWS credentials resolved (set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or an instance role)",
                reason="no-credentials",
            )

        try:
            async with self._get_client() as s3_client:
                await s3_client.head_bucket(Bucket=self.bucket_name)
        except Exception as exc:  # noqa: BLE001 — normalize any botocore/network error into a typed reason
            status_code = None
            error_code = None
            if hasattr(exc, "response") and isinstance(exc.response, dict):
                status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                error_code = exc.response.get("Error", {}).get("Code")

            if status_code == HTTPStatus.NOT_FOUND or error_code in {"404", "NoSuchBucket"}:
                return StorageReadiness(
                    ok=False,
                    backend="s3",
                    detail=f"bucket '{self.bucket_name}' does not exist",
                    reason="bucket-missing",
                )
            if status_code == HTTPStatus.FORBIDDEN or error_code in {"403", "AccessDenied", "InvalidAccessKeyId"}:
                return StorageReadiness(
                    ok=False,
                    backend="s3",
                    detail=f"access denied to bucket '{self.bucket_name}' (check credentials and bucket policy)",
                    reason="access-denied",
                )
            return StorageReadiness(
                ok=False,
                backend="s3",
                detail=f"could not reach bucket '{self.bucket_name}': {exc}",
                reason="unreachable",
            )

        return StorageReadiness(ok=True, backend="s3", detail=f"bucket reachable ({self.bucket_name})")

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        """Save a file to S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be saved
            data: The byte content of the file
            append: If True, append to existing file (not supported in S3, will raise error)

        Raises:
            Exception: If the file cannot be saved to S3
            NotImplementedError: If append=True (not supported in S3)
        """
        if append:
            msg = "Append mode is not supported for S3 storage"
            raise NotImplementedError(msg)

        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                put_params: dict[str, Any] = {
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "Body": data,
                    "Metadata": {MD5_METADATA_KEY: await asyncio.to_thread(_md5_hex, data)},
                }

                if self.tags:
                    tag_string = "&".join([f"{k}={v}" for k, v in self.tags.items()])
                    put_params["Tagging"] = tag_string

                await s3_client.put_object(**put_params)

            await logger.ainfo(f"File {file_name} saved successfully to S3: s3://{self.bucket_name}/{key}")

        except Exception as e:
            error_msg = str(e)
            error_code = None

            if hasattr(e, "response") and isinstance(e.response, dict):
                error_info = e.response.get("Error", {})
                error_code = error_info.get("Code")
                error_msg = error_info.get("Message", str(e))

            logger.exception(f"Error saving file {file_name} to S3 in flow {flow_id}: {error_msg}")

            if error_code == "NoSuchBucket":
                msg = f"S3 bucket '{self.bucket_name}' does not exist"
                raise FileNotFoundError(msg) from e
            if error_code == "AccessDenied":
                msg = "Access denied to S3 bucket. Please check your AWS credentials and bucket permissions"
                raise PermissionError(msg) from e
            if error_code == "InvalidAccessKeyId":
                msg = "Invalid AWS credentials. Please check your AWS access key and secret key"
                raise PermissionError(msg) from e
            msg = f"Failed to save file to S3: {error_msg}"
            raise RuntimeError(msg) from e

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be retrieved

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist in S3
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=key)
                content = await response["Body"].read()

            logger.debug(f"File {file_name} retrieved successfully from S3: s3://{self.bucket_name}/{key}")
        except Exception as e:
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") == "NoSuchKey":
                await logger.awarning(f"File {file_name} not found in S3 flow {flow_id}")
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e

            logger.exception(f"Error retrieving file {file_name} from S3 in flow {flow_id}")
            raise
        else:
            return content

    async def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Retrieve a file from S3 as a stream.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve
            chunk_size: Size of chunks to yield (default: 8192 bytes)

        Yields:
            bytes: Chunks of the file content

        Raises:
            FileNotFoundError: If the file does not exist in S3
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            # A stream holds its connection until the caller has read it all, which a slow
            # download can make as long as it likes. The shared client's 10 connections serve
            # every operation on this loop, so a stream gets a client of its own.
            async with self._get_client(shared=False) as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=key)
                body = response["Body"]

                try:
                    async for chunk in body.iter_chunks(chunk_size):
                        yield chunk
                finally:
                    if hasattr(body, "close"):
                        with contextlib.suppress(Exception):
                            await body.close()

        except Exception as e:
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") == "NoSuchKey":
                await logger.awarning(f"File {file_name} not found in S3 flow {flow_id}")
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e

            logger.exception(f"Error streaming file {file_name} from S3 in flow {flow_id}")
            raise

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specified S3 prefix (flow namespace).

        Args:
            flow_id: The flow/user identifier for namespacing

        Returns:
            list[str]: A list of file names (without the prefix)

        Raises:
            Exception: If there's an error listing files from S3
        """
        self._validate_identifiers(flow_id)

        prefix = self.build_full_path(flow_id, "")

        try:
            async with self._get_client() as s3_client:
                paginator = s3_client.get_paginator("list_objects_v2")
                files = []

                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            # Extract just the filename (remove the prefix)
                            full_key = obj["Key"]
                            # Remove the flow_id prefix to get just the filename
                            file_name = full_key[len(prefix) :]
                            if file_name:  # Skip the directory marker if it exists
                                files.append(file_name)

        except Exception:
            logger.exception(f"Error listing files in S3 flow {flow_id}")
            raise
        else:
            return files

    async def delete_namespace(self, namespace: str) -> int:
        """Delete every key under ``<prefix><namespace>/``, nested keys included."""
        validated = validate_namespace(namespace)
        prefix = f"{self.prefix}{validated}/"
        removed = 0
        try:
            async with self._get_client() as s3_client:
                paginator = s3_client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                    if not keys:
                        continue
                    response = await s3_client.delete_objects(
                        Bucket=self.bucket_name, Delete={"Objects": keys, "Quiet": True}
                    )
                    if response.get("Errors"):
                        msg = f"S3 refused to delete {len(response['Errors'])} object(s) in a namespace"
                        raise RuntimeError(msg)
                    removed += len(keys)
        except Exception:
            logger.exception("Error deleting an S3 namespace")
            raise
        return removed

    async def create_upload_link(
        self, flow_id: str, file_name: str, *, expires_in: int = UPLOAD_LINK_TTL, md5: str | None = None
    ) -> str:
        """A presigned ``PUT`` for exactly this key, good for ``expires_in`` seconds.

        See ``StorageService.create_upload_link``. Signing covers the bucket and the key, so a
        holder of the URL can write that one object and nothing else, and only until it expires.
        Nothing is contacted here: the URL is signed locally from the credentials already loaded.

        ``s3v4`` is pinned rather than left to the default, which resolves from the region:
        ``us-east-1`` reaches the legacy global endpoint and signs v2, and a v2 presigned PUT is
        refused by every region created since 2014 and by some MinIO setups.

        Tags are deliberately not signed in. Including them would oblige the uploader to send a
        matching ``x-amz-tagging`` header or get a signature mismatch, so the URL would no longer
        be self-contained. ``move_file`` applies the configured tags when the object is promoted.

        On AWS the link names the bucket's regional host. botocore presigns for the global
        ``<bucket>.s3.amazonaws.com``, which answers a bucket outside us-east-1 with a 307 to
        the regional host until its DNS settles, and a redirected PUT never lands. A custom
        endpoint (MinIO) keeps botocore's default, since a virtual host would put the bucket
        into that endpoint's hostname; so does a dotted bucket name, which breaks TLS there.

        With ``md5``, the link also signs the ``x-amz-meta-md5`` label and ``Content-MD5``, so
        the uploader must send both headers with those values. The label gives the stored
        object its checksum even in a bucket whose ETag is not one; ``Content-MD5`` is what
        makes S3 refuse a body that does not match it (``BadDigest``), since S3 never checks a
        label. Without it, a leaked link could replace a staged file with other bytes that
        still carry the expected label. Unlike tags this cannot be added at the promote: the
        promote's server-side copy never sees the bytes.

        Raises:
            ValueError: If ``md5`` is not 32 lowercase hex digits.
        """
        from urllib.parse import urlsplit

        from aiobotocore.config import AioConfig

        key = self.build_full_path(flow_id, file_name)
        if md5 is not None and not _MD5_PATTERN.fullmatch(md5):
            msg = f"Invalid md5 for {file_name}: expected 32 lowercase hex digits"
            raise ValueError(msg)
        async with self.session.create_client("s3") as probe:
            host = urlsplit(probe.meta.endpoint_url).hostname or ""
        regional = host.endswith(".amazonaws.com") and "." not in self.bucket_name
        config = AioConfig(signature_version="s3v4", s3={"addressing_style": "virtual"} if regional else None)
        async with self.session.create_client("s3", config=config) as s3_client:
            params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": key}
            if md5 is not None:
                params["Metadata"] = {MD5_METADATA_KEY: md5}
                params["ContentMD5"] = base64.b64encode(bytes.fromhex(md5)).decode()
            return await s3_client.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_in)

    async def move_file(self, source_namespace: str, target_namespace: str, file_name: str) -> None:
        """Move an object between namespaces with a server-side copy, then delete the source.

        See ``StorageService.move_file``. The copy runs inside S3, so the bytes never travel
        back through this process and the promote costs a metadata operation per file rather
        than a second upload.

        The configured tags are written here rather than inherited from the source. A staged
        object that arrived through ``create_upload_link`` carries no tags, and ``copy_object``
        copies the source's by default, so inheriting would leave a deployed project's files
        untagged while every file written through ``save_file`` is tagged, and any lifecycle or
        cost rule keyed on those tags would quietly skip them. Metadata, the ``md5`` label the
        upload link signed in among it, is copied as is.

        shortcut: ``copy_object`` tops out at 5 GiB per object; above that S3 wants
        ``upload_part_copy``. Add that when a single stored file reaches that size.
        """
        _refuse_bad_move(source_namespace, target_namespace, file_name)
        source_key = self.build_full_path(source_namespace, file_name)
        target_key = self.build_full_path(target_namespace, file_name)
        extra: dict[str, Any] = {}
        if self.tags:
            extra["Tagging"] = "&".join([f"{k}={v}" for k, v in self.tags.items()])
            extra["TaggingDirective"] = "REPLACE"

        async with self._get_client() as s3_client:
            try:
                await s3_client.copy_object(
                    Bucket=self.bucket_name,
                    Key=target_key,
                    CopySource={"Bucket": self.bucket_name, "Key": source_key},
                    **extra,
                )
            except Exception as e:
                if not (hasattr(e, "response") and e.response.get("Error", {}).get("Code") in ["NoSuchKey", "404"]):
                    logger.exception(f"Error moving file {file_name} from {source_namespace} to {target_namespace}")
                    raise
                # Checked on this client rather than through _has_object, which would open a
                # second one while this context is still held.
                try:
                    await s3_client.head_object(Bucket=self.bucket_name, Key=target_key)
                except Exception as head_error:
                    code = getattr(head_error, "response", {}).get("Error", {}).get("Code")
                    if code not in ["NoSuchKey", "404"]:
                        raise
                    msg = f"File not found: {file_name}"
                    raise FileNotFoundError(msg) from e
                return
            await s3_client.delete_object(Bucket=self.bucket_name, Key=source_key)

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be deleted

        Note:
            S3 delete_object doesn't raise an error if the object doesn't exist
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                await s3_client.delete_object(Bucket=self.bucket_name, Key=key)

        except Exception:
            logger.exception(f"Error deleting file {file_name} from S3 in flow {flow_id}")
            raise

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the file does not exist in S3
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                response = await s3_client.head_object(Bucket=self.bucket_name, Key=key)
                file_size = response["ContentLength"]

        except Exception as e:
            # Check if it's a 404 error
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") in ["NoSuchKey", "404"]:
                await logger.awarning(f"File {file_name} not found in S3 flow {flow_id}")
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e

            logger.exception(f"Error getting file size for {file_name} in S3 flow {flow_id}")
            raise
        else:
            return file_size

    async def get_file_md5(self, flow_id: str, file_name: str) -> str | None:
        """The object's MD5 from its ETag or its ``md5`` label (see ``md5_from_head``), otherwise None.

        Raises:
            FileNotFoundError: If the object does not exist, as ``get_file_size`` does.
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)
        try:
            async with self._get_client() as s3_client:
                response = await s3_client.head_object(Bucket=self.bucket_name, Key=key)
        except Exception as e:
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") in ["NoSuchKey", "404"]:
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e
            raise
        return md5_from_head(response)

    async def save_file_stream(self, flow_id: str, file_name: str, chunks: AsyncIterator[bytes]) -> int:
        """Save a file from a stream of chunks, holding one part in memory at a time.

        A body smaller than one part is a single ``put_object``; anything larger is a
        multipart upload, aborted if any part fails so no partial object is left behind.
        Returns the number of bytes written.

        The ``md5`` label goes on as ``save_file``'s does. A multipart upload fixes its metadata
        when it starts, before the checksum is known, so it is set afterwards by a server-side
        copy of the object onto itself; if that copy fails the file stays, unlabelled.
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)
        extra: dict[str, Any] = {}
        if self.tags:
            extra["Tagging"] = "&".join([f"{k}={v}" for k, v in self.tags.items()])

        async with self._get_client() as s3_client:
            buffer = bytearray()
            written = 0
            digest = hashlib.md5(usedforsecurity=False)
            upload_id: str | None = None
            parts: list[dict[str, Any]] = []

            async def upload_part(body: bytes) -> None:
                response = await s3_client.upload_part(
                    Bucket=self.bucket_name, Key=key, UploadId=upload_id, PartNumber=len(parts) + 1, Body=body
                )
                parts.append({"ETag": response["ETag"], "PartNumber": len(parts) + 1})

            try:
                async for chunk in chunks:
                    buffer += chunk
                    written += len(chunk)
                    digest.update(chunk)
                    while len(buffer) >= STREAM_PART_SIZE:
                        if upload_id is None:
                            created = await s3_client.create_multipart_upload(Bucket=self.bucket_name, Key=key, **extra)
                            upload_id = created["UploadId"]
                        await upload_part(bytes(buffer[:STREAM_PART_SIZE]))
                        del buffer[:STREAM_PART_SIZE]
                label = {MD5_METADATA_KEY: digest.hexdigest()}
                if upload_id is None:
                    await s3_client.put_object(
                        Bucket=self.bucket_name, Key=key, Body=bytes(buffer), Metadata=label, **extra
                    )
                    return written
                if buffer:
                    await upload_part(bytes(buffer))
                await s3_client.complete_multipart_upload(
                    Bucket=self.bucket_name, Key=key, UploadId=upload_id, MultipartUpload={"Parts": parts}
                )
            except BaseException:
                if upload_id is not None:
                    with contextlib.suppress(Exception):
                        await s3_client.abort_multipart_upload(Bucket=self.bucket_name, Key=key, UploadId=upload_id)
                raise
            try:
                await s3_client.copy_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    CopySource={"Bucket": self.bucket_name, "Key": key},
                    Metadata=label,
                    MetadataDirective="REPLACE",
                )
            except Exception:  # noqa: BLE001 - the file is stored; only its checksum label is missing
                await logger.awarning(f"Stored {file_name} without its md5 label; a deploy will read it to compare")
        return written

    async def teardown(self) -> None:
        """Close the clients this service built.

        Assumes no operation is in flight: a client still in use is closed under it.
        A client is closed on its own loop: this loop's here, a running loop's by a
        close scheduled on it. A loop that has stopped closes its own when it shuts down.
        """
        self._generation += 1
        loop = asyncio.get_running_loop()
        clients, self._clients = self._clients, {}
        for owner, (holder, _) in clients.items():
            if owner is loop:
                await holder.aclose()
            elif owner.is_running():
                asyncio.run_coroutine_threadsafe(holder.aclose(), owner)
        logger.info("S3 storage service teardown complete")
