"""S3StorageService builds one client per event loop, not one per operation.

Runs against a real S3-compatible server. Set ``AWS_ACCESS_KEY_ID`` and
``AWS_SECRET_ACCESS_KEY``, and ``AWS_ENDPOINT_URL`` to point at MinIO instead of AWS.
The bucket comes from ``LANGFLOW_OBJECT_STORAGE_BUCKET_NAME`` (default ``langflow-ci``)
and is created if it does not exist; each test works under its own prefix and
removes what it wrote.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
import threading
import uuid
from types import SimpleNamespace

import pytest
from langflow.services.storage.s3 import S3StorageService

pytestmark = pytest.mark.api_key_required

OPERATIONS_PER_FILE = 4  # save, get, size, delete


@pytest.fixture
def aws_credentials():
    missing = [name for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY") if not os.environ.get(name)]
    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")


@pytest.fixture
async def service(aws_credentials):  # noqa: ARG001
    settings = SimpleNamespace(
        config_dir=tempfile.gettempdir(),
        object_storage_bucket_name=os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci"),
        object_storage_prefix=f"client-reuse-{uuid.uuid4().hex[:8]}",
        object_storage_tags=None,
    )
    storage = S3StorageService(SimpleNamespace(), SimpleNamespace(settings=settings))
    async with storage.session.create_client("s3") as s3:
        with contextlib.suppress(s3.exceptions.BucketAlreadyOwnedByYou):
            await s3.create_bucket(Bucket=storage.bucket_name)
    yield storage
    await storage.teardown()


@pytest.fixture
def client_count(service):
    """Count the clients the service builds, while still building real ones."""
    created = []
    real_create_client = service.session.create_client

    def counting_create_client(*args, **kwargs):
        created.append(threading.get_ident())
        return real_create_client(*args, **kwargs)

    service.session.create_client = counting_create_client
    return created


async def _round_trip(storage: S3StorageService, files: int) -> None:
    namespace = uuid.uuid4().hex
    for index in range(files):
        name = f"file-{index}.txt"
        await storage.save_file(namespace, name, b"bytes")
        assert await storage.get_file(namespace, name) == b"bytes"
        assert await storage.get_file_size(namespace, name) == len(b"bytes")
        await storage.delete_file(namespace, name)


class TestClientReuse:
    async def test_many_operations_share_one_client(self, service, client_count):
        await _round_trip(service, files=5)

        assert len(client_count) == 1, f"{5 * OPERATIONS_PER_FILE} operations built {len(client_count)} clients"

    async def test_another_event_loop_gets_a_client_of_its_own(self, service, client_count):
        await _round_trip(service, files=2)

        # A client belongs to the loop it was made on. Components and CLI paths
        # can reach the service from a loop of their own, so that loop needs its own.
        errors: list[BaseException] = []

        def other_loop() -> None:
            try:
                asyncio.run(_round_trip(service, files=2))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=other_loop)
        thread.start()
        thread.join()

        assert errors == []
        assert len(client_count) == 2
        # And the original loop keeps using the one it already had.
        await _round_trip(service, files=1)
        assert len(client_count) == 2

    async def test_teardown_closes_the_client_and_the_next_call_builds_a_new_one(self, service, client_count):
        await _round_trip(service, files=1)
        await service.teardown()

        await _round_trip(service, files=1)

        assert len(client_count) == 2
