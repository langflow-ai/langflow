"""AWS S3 (and S3-compatible) ingestion source.

Walks a bucket / prefix via boto3 and yields each matching object as
an ``IngestionItem``. Content is fetched on demand during
``fetch_content`` so a bucket with thousands of objects doesn't
balloon memory during the list phase.

Credentials + endpoint URL are resolved from Langflow variables
(``source_config`` carries the variable *names*, not the secrets
themselves). That keeps the ``ingestion_run.source_config`` column
safe to round-trip back to the UI and lets operators rotate keys
through the existing variable-settings UI.

S3-compatible services (MinIO, Cloudflare R2, Wasabi, etc.) work by
setting ``endpoint_url_variable`` and optionally ``region_variable``.
"""

from __future__ import annotations

import asyncio
import mimetypes
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    SourceType,
)
from lfx.base.knowledge_bases.ingestion_sources.connector_base import KBConnectorSource

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Default extension allow-list — matches FolderSource so the two
# flows produce comparable result sets on identical datasets.
DEFAULT_EXTENSIONS: tuple[str, ...] = (
    "txt",
    "md",
    "markdown",
    "rst",
    "csv",
    "tsv",
    "json",
    "jsonl",
    "yaml",
    "yml",
    "xml",
    "html",
    "htm",
    "pdf",
    "docx",
    "doc",
    "pptx",
    "ppt",
    "xlsx",
    "xls",
)

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
DEFAULT_ACCESS_KEY_VARIABLE = "AWS_ACCESS_KEY_ID"
DEFAULT_SECRET_KEY_VARIABLE = "AWS_SECRET_ACCESS_KEY"  # noqa: S105 — variable NAME, not the secret  # pragma: allowlist secret
DEFAULT_SESSION_TOKEN_VARIABLE = "AWS_SESSION_TOKEN"  # noqa: S105 — variable NAME, not the secret  # pragma: allowlist secret


class S3Source(KBConnectorSource):
    """Walks ``bucket``/``prefix`` on AWS S3 (or S3-compatible).

    ``source_config`` shape::

        {
            "bucket": "my-bucket",
            "prefix": "docs/",                         # optional
            "extensions": ["pdf", "md"],               # optional
            "max_file_size_bytes": 10_000_000,         # optional
            "access_key_variable": "AWS_ACCESS_KEY_ID", # variable name
            "secret_key_variable": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
            "session_token_variable": "AWS_SESSION_TOKEN",  # optional (STS)  # pragma: allowlist secret
            "region_variable": "AWS_REGION",            # optional
            "endpoint_url_variable": "S3_ENDPOINT_URL", # optional (S3-compatible)
        }
    """

    source_type = SourceType.S3
    display_name = "AWS S3"
    description = "Ingest every matching object from an S3 bucket or prefix."
    icon = "cloud"
    requires_credentials = True

    async def validate_config(self) -> None:
        bucket = self.source_config.get("bucket")
        if not bucket or not isinstance(bucket, str):
            msg = "S3Source requires a 'bucket' string in source_config."
            raise ValueError(msg)

        access_variable = self.source_config.get("access_key_variable") or DEFAULT_ACCESS_KEY_VARIABLE
        secret_variable = self.source_config.get("secret_key_variable") or DEFAULT_SECRET_KEY_VARIABLE

        # Resolve early so credential problems surface as a 400 on the
        # API route rather than as a silent empty result.
        await self.resolve_required_secret(access_variable)
        await self.resolve_required_secret(secret_variable)

        max_size = self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES)
        if not isinstance(max_size, int) or max_size <= 0:
            msg = "max_file_size_bytes must be a positive integer."
            raise ValueError(msg)

    async def _build_client(self):
        """Instantiate a boto3 S3 client with credentials from variables.

        boto3 is imported lazily so environments that never touch S3
        don't pay its import cost. The client is created fresh per run
        because underlying ``botocore`` sessions are not safe to share
        across unrelated request contexts.
        """
        try:
            import boto3
        except ImportError as exc:
            msg = "boto3 is required for S3 ingestion. Install the 's3' extras or add boto3 to your environment."
            raise RuntimeError(msg) from exc

        access_variable = self.source_config.get("access_key_variable") or DEFAULT_ACCESS_KEY_VARIABLE
        secret_variable = self.source_config.get("secret_key_variable") or DEFAULT_SECRET_KEY_VARIABLE
        session_token_variable = self.source_config.get("session_token_variable") or DEFAULT_SESSION_TOKEN_VARIABLE
        region_variable = self.source_config.get("region_variable")
        endpoint_url_variable = self.source_config.get("endpoint_url_variable")

        access_key = await self.resolve_required_secret(access_variable)
        secret_key = await self.resolve_required_secret(secret_variable)
        session_token = await self.resolve_secret(session_token_variable)
        region = await self.resolve_secret(region_variable) if region_variable else None
        endpoint_url = await self.resolve_secret(endpoint_url_variable) if endpoint_url_variable else None

        client_kwargs: dict[str, Any] = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        if session_token:
            client_kwargs["aws_session_token"] = session_token
        if region:
            client_kwargs["region_name"] = region
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        # boto3.client construction does disk + config I/O (loading
        # botocore data, parsing ~/.aws). Run it off the event loop.
        return await asyncio.to_thread(boto3.client, "s3", **client_kwargs)

    def _matches_extension(self, key: str, allowed: tuple[str, ...]) -> bool:
        if "." not in key:
            # Extensionless objects get through unless the operator
            # explicitly trimmed the allow-list.
            return True
        ext = key.rsplit(".", 1)[-1].lower()
        return ext in allowed

    def _normalized_extensions(self) -> tuple[str, ...]:
        raw = self.source_config.get("extensions")
        if raw is None:
            return DEFAULT_EXTENSIONS
        normalized = tuple(ext.lower().lstrip(".") for ext in raw if ext)
        return normalized or DEFAULT_EXTENSIONS

    def _max_size(self) -> int:
        return int(self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES))

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        bucket = self.source_config["bucket"]
        prefix = self.source_config.get("prefix") or ""
        extensions = self._normalized_extensions()
        max_size = self._max_size()

        client = await self._build_client()
        paginator = client.get_paginator("list_objects_v2")

        # boto3 paginator is a sync iterable over HTTP calls. Fetch
        # one page per thread hop so the event loop stays free between
        # pages.
        def _fetch_next_page(iterator: Any) -> dict[str, Any] | None:
            try:
                return next(iterator)
            except StopIteration:
                return None

        page_iter = iter(paginator.paginate(Bucket=bucket, Prefix=prefix))
        while True:
            page = await asyncio.to_thread(_fetch_next_page, page_iter)
            if page is None:
                break
            for obj in page.get("Contents", []) or []:
                key = obj.get("Key")
                if not key or key.endswith("/"):
                    # Directory marker — skip.
                    continue
                if not self._matches_extension(key, extensions):
                    continue
                size = int(obj.get("Size") or 0)
                if size > max_size:
                    continue

                yield IngestionItem(
                    item_id=key,
                    display_name=key.rsplit("/", 1)[-1],
                    mime_type=mimetypes.guess_type(key)[0],
                    source_url=f"s3://{bucket}/{key}",
                    source_metadata={
                        "bucket": bucket,
                        "key": key,
                        "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                        "etag": (obj.get("ETag") or "").strip('"'),
                    },
                    size_bytes=size,
                )

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        bucket = self.source_config["bucket"]
        client = await self._build_client()

        def _download() -> bytes:
            response = client.get_object(Bucket=bucket, Key=item.item_id)
            return response["Body"].read()

        body = await asyncio.to_thread(_download)
        file_name = item.item_id.rsplit("/", 1)[-1] or item.item_id
        return IngestionItemContent(raw_bytes=bytes(body), file_name=file_name)

    def describe(self) -> dict[str, Any]:
        """Surface everything except the (already variable-only) credentials."""
        base = super().describe()
        base["config"] = {
            "bucket": self.source_config.get("bucket"),
            "prefix": self.source_config.get("prefix"),
            "extensions": list(self._normalized_extensions()),
            "max_file_size_bytes": self._max_size(),
            "access_key_variable": self.source_config.get("access_key_variable") or DEFAULT_ACCESS_KEY_VARIABLE,
            "secret_key_variable": self.source_config.get("secret_key_variable") or DEFAULT_SECRET_KEY_VARIABLE,
            "session_token_variable": self.source_config.get("session_token_variable")
            or DEFAULT_SESSION_TOKEN_VARIABLE,
            "region_variable": self.source_config.get("region_variable"),
            "endpoint_url_variable": self.source_config.get("endpoint_url_variable"),
        }
        return base
