"""Unit tests for ``S3Source``.

Mocks ``boto3`` at the module level so tests don't need real AWS
credentials or network access. Exercises every code path in the
HMAC + S3-compatible surface: config validation, credential
resolution, bucket walk with paginator, extension filter, size cap,
and object fetch.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.knowledge_bases.ingestion_sources import S3Source, SourceType


@pytest.fixture
def fake_paginator():
    """Return a paginator-like object that yields preset pages."""
    paginator = MagicMock()
    paginator.paginate = MagicMock(
        return_value=[
            {
                "Contents": [
                    {"Key": "docs/alpha.md", "Size": 100, "LastModified": _fake_dt(), "ETag": '"abc"'},
                    {"Key": "docs/big.pdf", "Size": 999_999_999, "LastModified": _fake_dt(), "ETag": '"big"'},
                    {"Key": "images/logo.png", "Size": 50, "LastModified": _fake_dt(), "ETag": '"png"'},
                    {"Key": "docs/subfolder/", "Size": 0, "LastModified": _fake_dt(), "ETag": '""'},
                    {"Key": "docs/beta.txt", "Size": 200, "LastModified": _fake_dt(), "ETag": '"def"'},
                ],
            },
        ],
    )
    return paginator


def _fake_dt():
    from datetime import datetime, timezone

    return datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)


def _make_client(paginator: MagicMock, body_by_key: dict[str, bytes]):
    """Build a fake boto3 S3 client that returns ``paginator`` and canned bodies."""
    client = MagicMock()
    client.get_paginator = MagicMock(return_value=paginator)

    def fake_get_object(*, Bucket, Key):  # noqa: ARG001, N803 — boto3 signature
        body = MagicMock()
        body.read = MagicMock(return_value=body_by_key[Key])
        return {"Body": body}

    client.get_object = MagicMock(side_effect=fake_get_object)
    return client


class TestS3SourceValidation:
    async def test_requires_bucket(self):
        source = S3Source(user_id=None, source_config={})
        with pytest.raises(ValueError, match="'bucket' string"):
            await source.validate_config()

    async def test_missing_credentials_raises(self, monkeypatch):
        # No env fallback, no variable service value.
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        source = S3Source(user_id=None, source_config={"bucket": "demo"})
        with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID"):
            await source.validate_config()

    async def test_env_vars_satisfy_credentials(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")
        source = S3Source(user_id=None, source_config={"bucket": "demo"})
        # No raise → the env-var fallback resolved both.
        await source.validate_config()

    async def test_rejects_non_positive_max_size(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")
        source = S3Source(
            user_id=None,
            source_config={"bucket": "demo", "max_file_size_bytes": 0},
        )
        with pytest.raises(ValueError, match="positive integer"):
            await source.validate_config()


class TestS3SourceListing:
    async def test_list_items_applies_filters(self, monkeypatch, fake_paginator):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")
        client = _make_client(fake_paginator, body_by_key={})

        source = S3Source(
            user_id=None,
            source_config={"bucket": "demo", "prefix": "docs/"},
        )
        with patch.object(source, "_build_client", new=AsyncMock(return_value=client)):
            items = [item async for item in source.list_items()]

        keys = [i.item_id for i in items]
        # Filtered: big.pdf (oversized), logo.png (extension), trailing / (directory).
        assert keys == ["docs/alpha.md", "docs/beta.txt"]
        assert items[0].source_url == "s3://demo/docs/alpha.md"
        assert items[0].source_metadata["bucket"] == "demo"
        assert items[0].source_metadata["etag"] == "abc"  # quotes stripped
        assert items[0].size_bytes == 100

    async def test_list_items_respects_custom_extensions(self, monkeypatch, fake_paginator):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")
        client = _make_client(fake_paginator, body_by_key={})

        source = S3Source(
            user_id=None,
            source_config={"bucket": "demo", "extensions": ["png"]},
        )
        with patch.object(source, "_build_client", new=AsyncMock(return_value=client)):
            items = [item async for item in source.list_items()]
        keys = [i.item_id for i in items]
        assert keys == ["images/logo.png"]

    async def test_list_items_size_cap(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")
        paginator = MagicMock()
        paginator.paginate = MagicMock(
            return_value=[
                {
                    "Contents": [
                        {"Key": "small.txt", "Size": 500, "LastModified": _fake_dt(), "ETag": '"s"'},
                        {"Key": "large.txt", "Size": 9_000_000, "LastModified": _fake_dt(), "ETag": '"l"'},
                    ],
                },
            ],
        )
        client = _make_client(paginator, body_by_key={})
        source = S3Source(
            user_id=None,
            source_config={"bucket": "demo", "max_file_size_bytes": 1_000_000},
        )
        with patch.object(source, "_build_client", new=AsyncMock(return_value=client)):
            items = [item async for item in source.list_items()]
        assert [i.item_id for i in items] == ["small.txt"]


class TestS3SourceFetch:
    async def test_fetch_content_returns_bytes_and_filename(self, monkeypatch, fake_paginator):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")
        body_by_key = {"docs/alpha.md": b"# Alpha"}
        client = _make_client(fake_paginator, body_by_key=body_by_key)

        source = S3Source(user_id=None, source_config={"bucket": "demo"})
        with patch.object(source, "_build_client", new=AsyncMock(return_value=client)):
            items = [item async for item in source.list_items()]
            content = await source.fetch_content(items[0])

        assert content.raw_bytes == b"# Alpha"
        # fetch_content strips the prefix for text-extractor dispatch.
        assert content.file_name == "alpha.md"


class TestS3SourceDescribe:
    def test_describe_exposes_variable_names_not_secrets(self):
        source = S3Source(
            user_id=None,
            source_config={
                "bucket": "demo",
                "prefix": "docs/",
                "access_key_variable": "MY_AWS_ID",
                "secret_key_variable": "MY_AWS_KEY",  # pragma: allowlist secret - variable NAME, not the secret
                "endpoint_url_variable": "MY_ENDPOINT",
            },
        )
        described = source.describe()
        assert described["source_type"] == SourceType.S3.value
        config = described["config"]
        # Variable names are safe to echo; the resolved secret values never appear.
        assert config["access_key_variable"] == "MY_AWS_ID"
        assert config["secret_key_variable"] == "MY_AWS_KEY"  # noqa: S105 — variable name, not a secret  # pragma: allowlist secret
        assert config["endpoint_url_variable"] == "MY_ENDPOINT"
        assert "aws_secret_access_key" not in config
        assert config["bucket"] == "demo"
        assert config["prefix"] == "docs/"
