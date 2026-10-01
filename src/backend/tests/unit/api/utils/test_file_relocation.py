"""Tests for moving uploaded file bytes to object storage.

The copy runs against a real S3-compatible server, because the failure modes worth
covering are its own: a key that is already there, an object that comes back a
different size, a byte range that never arrives. Set ``AWS_ACCESS_KEY_ID`` and
``AWS_SECRET_ACCESS_KEY`` to run them, and ``AWS_ENDPOINT_URL`` to point at MinIO
instead of AWS.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
from langflow.api.utils.file_relocation import NoSuchUserError, SourceNotLocalError, relocate_files
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope

if TYPE_CHECKING:
    from pathlib import Path


def _s3_configured() -> bool:
    return bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))


pytestmark = [
    # The repo marks tests that need real credentials, so the unit lane deselects them.
    pytest.mark.api_key_required,
    pytest.mark.skipif(not _s3_configured(), reason="AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY not set"),
]


@pytest.fixture
async def bucket() -> str:
    """A bucket of this test's own, emptied and removed afterwards."""
    from aiobotocore.session import get_session

    name = f"lf-relocate-{uuid.uuid4().hex[:10]}"
    session = get_session()
    async with session.create_client("s3") as s3:
        await s3.create_bucket(Bucket=name)
    try:
        yield name
    finally:
        async with session.create_client("s3") as s3:
            listing = await s3.list_objects_v2(Bucket=name)
            for obj in listing.get("Contents", []):
                await s3.delete_object(Bucket=name, Key=obj["Key"])
            await s3.delete_bucket(Bucket=name)


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point local storage at a directory this test owns."""
    root = tmp_path / "storage"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(root))
    monkeypatch.setattr(get_storage_service(), "data_dir", anyio.Path(root))
    return root


async def _stored_keys(bucket: str, prefix: str = "") -> list[str]:
    from aiobotocore.session import get_session

    async with get_session().create_client("s3") as s3:
        listing = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return sorted(obj["Key"] for obj in listing.get("Contents", []))


async def _seed_user_file(storage_dir: Path, owner: uuid.UUID, *, name: str, data: bytes) -> str:
    """One uploaded file: a row, and its bytes where local storage keeps them."""
    async with session_scope() as session:
        session.add(File(user_id=owner, name=name.rsplit(".", 1)[0], path=f"{owner}/{name}", size=len(data)))
        await session.commit()

    owner_dir = storage_dir / str(owner)
    owner_dir.mkdir(parents=True, exist_ok=True)
    (owner_dir / name).write_bytes(data)
    return name


class TestRelocateFiles:
    async def test_copies_bytes_under_the_same_logical_key(self, active_user, storage_dir, bucket):
        user_id = active_user.id
        name = await _seed_user_file(storage_dir, user_id, name="report.pdf", data=b"pdf-bytes")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["copied"]
        assert await _stored_keys(bucket) == [f"files/{user_id}/{name}"]

    async def test_rerunning_skips_what_is_already_there(self, active_user, storage_dir, bucket):
        await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        assert [r.status for r in await relocate_files(target_bucket=bucket, target_prefix="files")] == ["copied"]

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["skipped"]

    async def test_a_row_whose_bytes_are_gone_is_reported_not_skipped(self, active_user, storage_dir, bucket):
        name = await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        (storage_dir / str(active_user.id) / name).unlink()

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["failed"]
        assert "no bytes" in (results[0].reason or "")
        assert await _stored_keys(bucket) == []

    async def test_dry_run_writes_nothing(self, active_user, storage_dir, bucket):
        await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")

        results = await relocate_files(target_bucket=bucket, target_prefix="files", dry_run=True)

        assert [r.status for r in results] == ["would_copy"]
        assert await _stored_keys(bucket) == []

    async def test_a_target_object_of_a_different_size_is_refused(self, active_user, storage_dir, bucket):
        from aiobotocore.session import get_session

        user_id = active_user.id
        name = await _seed_user_file(storage_dir, user_id, name="report.pdf", data=b"pdf-bytes")
        async with get_session().create_client("s3") as s3:
            await s3.put_object(Bucket=bucket, Key=f"files/{user_id}/{name}", Body=b"something else entirely")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["failed"]
        assert "different size" in (results[0].reason or "")


class TestFlowScopedUploads:
    """Files uploaded to a flow have no row anywhere: the storage namespace is the only record."""

    async def test_a_flow_upload_is_copied_too(self, active_user, storage_dir, bucket):
        async with session_scope() as session:
            flow = Flow(name=f"flow-{uuid.uuid4().hex[:6]}", user_id=active_user.id, data={"nodes": []})
            session.add(flow)
            await session.commit()
            await session.refresh(flow)
            flow_id = flow.id
        flow_dir = storage_dir / str(flow_id)
        flow_dir.mkdir(parents=True)
        (flow_dir / "2026-01-01_notes.txt").write_bytes(b"attached to a flow")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["copied"]
        assert await _stored_keys(bucket) == [f"files/{flow_id}/2026-01-01_notes.txt"]


class TestRefusals:
    async def test_an_s3_source_is_refused_before_anything_is_read(self, active_user, storage_dir, bucket):
        """The docs used to end here: switch to s3, then run this, and read the bucket onto itself."""
        await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        settings = get_settings_service().settings
        monkey = pytest.MonkeyPatch()
        monkey.setattr(settings, "storage_type", "s3")
        try:
            with pytest.raises(SourceNotLocalError, match="LANGFLOW_STORAGE_TYPE"):
                await relocate_files(target_bucket=bucket, target_prefix="files")
        finally:
            monkey.undo()
        assert await _stored_keys(bucket) == []

    async def test_a_username_nobody_has_is_refused(self, active_user, storage_dir, bucket):  # noqa: ARG002
        with pytest.raises(NoSuchUserError, match="nobody"):
            await relocate_files(target_bucket=bucket, target_prefix="files", username="nobody")


class TestOneBadNameDoesNotStopTheRest:
    async def test_a_name_object_storage_rejects_is_reported(self, active_user, storage_dir, bucket):
        """Uploads reject `..` today, so a name like this is a row from before that guard."""
        for name in ("aaa_first.txt", "legacy..name.txt", "zzz_last.txt"):
            await _seed_user_file(storage_dir, active_user.id, name=name, data=b"bytes")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert sorted(r.status for r in results) == ["copied", "copied", "failed"]
        failed = next(r for r in results if r.status == "failed")
        assert failed.file_name == "legacy..name.txt"
        assert len(await _stored_keys(bucket)) == 2


class TestWhatGetsFound:
    async def test_a_file_with_no_row_is_copied(self, active_user, storage_dir, bucket):
        """Ephemeral chat uploads write bytes under the user id and record no row."""
        owner_dir = storage_dir / str(active_user.id)
        owner_dir.mkdir(parents=True, exist_ok=True)
        (owner_dir / "chat-attachment.png").write_bytes(b"png-bytes")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["copied"]
        assert await _stored_keys(bucket) == [f"files/{active_user.id}/chat-attachment.png"]

    async def test_a_dry_run_does_not_read_the_bytes(self, active_user, storage_dir, bucket):
        """A dry run over a real instance would otherwise pull every file into memory."""
        await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        reads = []
        original = type(get_storage_service()).get_file

        async def counted(self, *args, **kwargs):
            reads.append(kwargs.get("file_name"))
            return await original(self, *args, **kwargs)

        monkey = pytest.MonkeyPatch()
        monkey.setattr(type(get_storage_service()), "get_file", counted)
        try:
            results = await relocate_files(target_bucket=bucket, target_prefix="files", dry_run=True)
        finally:
            monkey.undo()

        assert [r.status for r in results] == ["would_copy"]
        assert reads == []

    async def test_a_flow_with_no_uploads_is_not_looked_up(self, active_user, storage_dir, bucket, caplog):  # noqa: ARG002
        """One warning per flow buries the report on an instance with many flows."""
        async with session_scope() as session:
            for _ in range(3):
                session.add(Flow(name=f"flow-{uuid.uuid4().hex[:6]}", user_id=active_user.id, data={"nodes": []}))
            await session.commit()

        with caplog.at_level("WARNING"):
            await relocate_files(target_bucket=bucket, target_prefix="files")

        assert "does not exist" not in caplog.text


class TestPlanAndVerify:
    """The decision and the check stand alone, so a sync can show its plan before anything moves."""

    async def test_plan_decides_without_writing_or_reading_the_body(self, active_user, storage_dir, bucket):
        from langflow.api.utils.file_relocation import _target_storage, plan_file

        name = await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        source = get_storage_service()
        reads = []
        original = type(source).get_file

        async def counted(self, *args, **kwargs):
            reads.append(kwargs.get("file_name"))
            return await original(self, *args, **kwargs)

        monkey = pytest.MonkeyPatch()
        monkey.setattr(type(source), "get_file", counted)
        target = _target_storage(bucket, "files", None)
        try:
            plan = await plan_file(source, target, str(active_user.id), name)
        finally:
            monkey.undo()

        assert (plan.action, plan.size) == ("copy", len(b"pdf-bytes"))
        assert reads == []
        assert await _stored_keys(bucket) == []

    async def test_verify_says_why_the_target_does_not_match(self, active_user, storage_dir, bucket):  # noqa: ARG002
        from aiobotocore.session import get_session
        from langflow.api.utils.file_relocation import _target_storage, verify_file

        owner = str(active_user.id)
        async with get_session().create_client("s3") as s3:
            await s3.put_object(Bucket=bucket, Key=f"files/{owner}/report.pdf", Body=b"short")
        target = _target_storage(bucket, "files", None)

        problem = await verify_file(target, owner, "report.pdf", expected_size=9)

        assert problem is not None
        assert "5 bytes" in problem
        assert "9 bytes" in problem
        assert await verify_file(target, owner, "report.pdf", expected_size=5) is None


class TestIdentityOnRerun:
    async def test_same_size_different_content_is_refused_not_skipped(self, active_user, storage_dir, bucket):
        """A file edited between runs can keep its length. Size alone would call it carried."""
        from aiobotocore.session import get_session

        name = await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        async with get_session().create_client("s3") as s3:
            await s3.put_object(Bucket=bucket, Key=f"files/{active_user.id}/{name}", Body=b"PDF-BYTES")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert [r.status for r in results] == ["failed"]
        assert "same size" in (results[0].reason or "")

    async def test_a_refusal_names_the_source_size(self, active_user, storage_dir, bucket):
        """A large file failing looks like any other failure unless the report says how large."""
        from aiobotocore.session import get_session

        name = await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        async with get_session().create_client("s3") as s3:
            await s3.put_object(Bucket=bucket, Key=f"files/{active_user.id}/{name}", Body=b"longer than nine")

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert "9 bytes" in (results[0].reason or "")


class TestLargeFiles:
    """A file is streamed across, so its size is not what the copy holds in memory."""

    async def _peak_while_copying(self, storage_dir, owner, bucket, *, name: str, size: int) -> tuple[int, str]:
        import hashlib
        import tracemalloc

        data = os.urandom(size)
        await _seed_user_file(storage_dir, owner, name=name, data=data)
        expected_md5 = hashlib.md5(data).hexdigest()  # noqa: S324 - a content check, not security
        del data

        tracemalloc.start()
        try:
            results = await relocate_files(target_bucket=bucket, target_prefix="files")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert {r.file_name: r.status for r in results}[name] == "copied"
        return peak, expected_md5

    async def test_memory_does_not_grow_with_file_size(self, active_user, storage_dir, bucket):
        import hashlib

        mib = 1024 * 1024
        small, _ = await self._peak_while_copying(storage_dir, active_user.id, bucket, name="small.bin", size=16 * mib)
        large, large_md5 = await self._peak_while_copying(
            storage_dir, active_user.id, bucket, name="large.bin", size=80 * mib
        )

        # A copy that held the file would peak at least 64 MiB higher for the larger one.
        assert large - small < 16 * mib, f"peak {small} bytes for 16 MiB, {large} bytes for 80 MiB"
        from aiobotocore.session import get_session

        async with get_session().create_client("s3") as s3:
            obj = await s3.get_object(Bucket=bucket, Key=f"files/{active_user.id}/large.bin")
            body = await obj["Body"].read()
        assert hashlib.md5(body).hexdigest() == large_md5  # noqa: S324

    async def test_a_large_file_already_there_is_skipped(self, active_user, storage_dir, bucket):
        await _seed_user_file(storage_dir, active_user.id, name="big.bin", data=os.urandom(20 * 1024 * 1024))
        assert [r.status for r in await relocate_files(target_bucket=bucket, target_prefix="files")] == ["copied"]

        again = await relocate_files(target_bucket=bucket, target_prefix="files")

        # Uploaded in parts, so its ETag is no MD5 and identity falls back to size.
        assert [(r.status, r.reason) for r in again] == [
            ("skipped", "already in the target (20971520 bytes, identity checked by size only)")
        ]


class TestConcurrency:
    async def test_every_file_is_copied_with_several_in_flight(self, active_user, storage_dir, bucket):
        for index in range(12):
            await _seed_user_file(storage_dir, active_user.id, name=f"f{index}.txt", data=f"bytes {index}".encode())

        results = await relocate_files(target_bucket=bucket, target_prefix="files", concurrency=4)

        assert sorted(r.status for r in results) == ["copied"] * 12
        assert len(await _stored_keys(bucket)) == 12


class TestTheCommandLeavesTheDatabaseAlone:
    """The command runs against a database the server has not booted on yet, so it must not run the server's startup."""

    async def _revisions(self) -> set[str]:
        from sqlalchemy import text

        async with session_scope() as session:
            return set((await session.exec(text("SELECT version_num FROM alembic_version"))).scalars())

    async def test_a_dry_run_prunes_and_migrates_nothing(self, active_user, storage_dir, bucket):
        from datetime import datetime, timezone

        from langflow.__main__ import _relocate_files
        from langflow.services.database.models.auth import AuthzAuditLog
        from sqlmodel import select

        await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        async with session_scope() as session:
            # Older than any retention window, so startup's history pruning would delete it.
            old = datetime(2020, 1, 1, tzinfo=timezone.utc)
            session.add(AuthzAuditLog(action="read", result="allow", timestamp=old))
        revisions = await self._revisions()

        failed = await _relocate_files(bucket=bucket, prefix="files", username=None, dry_run=True, concurrency=1)

        assert failed == 0
        async with session_scope() as session:
            assert len((await session.exec(select(AuthzAuditLog))).all()) == 1
        assert revisions
        assert await self._revisions() == revisions
        assert await _stored_keys(bucket) == []

    async def test_a_database_at_another_revision_is_refused(self, active_user, storage_dir, bucket):
        import typer
        from langflow.__main__ import _relocate_files
        from sqlalchemy import text

        await _seed_user_file(storage_dir, active_user.id, name="report.pdf", data=b"pdf-bytes")
        async with session_scope() as session:
            await session.exec(text("UPDATE alembic_version SET version_num = 'not_this_version'"))

        with pytest.raises(typer.Exit) as refused:
            await _relocate_files(bucket=bucket, prefix="files", username=None, dry_run=False, concurrency=1)

        assert refused.value.exit_code == 2
        assert await self._revisions() == {"not_this_version"}
        assert await _stored_keys(bucket) == []


class TestMissingObjects:
    async def test_md5_of_a_missing_key_is_file_not_found(self, active_user, storage_dir, bucket):  # noqa: ARG002
        from langflow.api.utils.file_relocation import _target_storage

        target = _target_storage(bucket, "files", None)
        try:
            with pytest.raises(FileNotFoundError):
                await target.get_file_md5(flow_id=str(active_user.id), file_name="nothing-here.txt")
        finally:
            await target.teardown()


class TestChatAttachmentPaths:
    """Chat history records each attachment's path, and on local storage that path is absolute.

    After the switch the S3 backend resolves a message's attachment from the path
    recorded in ``message.files``, so the move has to leave paths S3 can resolve.
    """

    async def _flow_with_attachment(self, storage_dir: Path, owner: uuid.UUID, name: str, data: bytes) -> uuid.UUID:
        async with session_scope() as session:
            flow = Flow(name=f"flow-{uuid.uuid4().hex[:6]}", user_id=owner, data={"nodes": []})
            session.add(flow)
            await session.commit()
            await session.refresh(flow)
            flow_id = flow.id
        (storage_dir / str(flow_id)).mkdir(parents=True)
        (storage_dir / str(flow_id) / name).write_bytes(data)
        return flow_id

    async def _message(self, flow_id: uuid.UUID, files: list[str]) -> uuid.UUID:
        async with session_scope() as session:
            message = MessageTable(
                sender="User",
                sender_name="User",
                session_id=str(flow_id),
                text="see attached",
                flow_id=flow_id,
                files=files,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message.id

    async def _files(self, message_id: uuid.UUID) -> list[str]:
        async with session_scope() as session:
            return list((await session.get(MessageTable, message_id)).files)

    async def _read_on_target(self, bucket: str, entry: str) -> bytes:
        from langflow.api.utils.file_relocation import _target_storage

        target = _target_storage(bucket, "files", None)
        try:
            namespace, name = target.parse_file_path(entry)
            return await target.get_file(flow_id=namespace, file_name=name)
        finally:
            await target.teardown()

    async def test_an_absolute_attachment_path_is_repointed_so_the_target_resolves_it(
        self, active_user, storage_dir, bucket
    ):
        flow_id = await self._flow_with_attachment(storage_dir, active_user.id, "photo.png", b"png-bytes")
        message_id = await self._message(flow_id, [str(storage_dir / str(flow_id) / "photo.png")])

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert await self._files(message_id) == [f"{flow_id}/photo.png"]
        assert await self._read_on_target(bucket, (await self._files(message_id))[0]) == b"png-bytes"
        assert [r.status for r in results if r.status == "repointed"] == ["repointed"]

        # A second run finds nothing left to repoint.
        again = await relocate_files(target_bucket=bucket, target_prefix="files")
        assert not [r for r in again if r.status == "repointed"]

    async def test_a_dry_run_reports_the_repoint_without_changing_the_message(self, active_user, storage_dir, bucket):
        flow_id = await self._flow_with_attachment(storage_dir, active_user.id, "photo.png", b"png-bytes")
        absolute = str(storage_dir / str(flow_id) / "photo.png")
        message_id = await self._message(flow_id, [absolute])

        results = await relocate_files(target_bucket=bucket, target_prefix="files", dry_run=True)

        assert await self._files(message_id) == [absolute]
        assert [r.status for r in results if r.status == "would_repoint"] == ["would_repoint"]

    async def test_the_command_prints_no_byte_count_for_a_repoint(self, active_user, storage_dir, bucket, capsys):
        from langflow.__main__ import _relocate_files

        flow_id = await self._flow_with_attachment(storage_dir, active_user.id, "photo.png", b"png-bytes")
        await self._message(flow_id, [str(storage_dir / str(flow_id) / "photo.png")])

        for dry_run in (True, False):
            await _relocate_files(bucket=bucket, prefix="files", username=None, dry_run=dry_run, concurrency=1)
        lines = capsys.readouterr().out.splitlines()

        repoints = [line for line in lines if line.startswith(("would_repoint", "repointed"))]
        assert len(repoints) == 2, lines
        assert not [line for line in repoints if "bytes" in line], repoints
        # A copy still says how much it moved.
        assert [line for line in lines if line.startswith("copied") and "9 bytes" in line], lines

    async def test_a_path_recorded_under_another_config_dir_is_repointed_when_storage_holds_the_file(
        self, active_user, storage_dir, bucket
    ):
        # The instance ran from another directory before the backup was restored here.
        flow_id = await self._flow_with_attachment(storage_dir, active_user.id, "notes.txt", b"notes")
        message_id = await self._message(flow_id, [f"/var/lib/langflow/{flow_id}/notes.txt"])

        await relocate_files(target_bucket=bucket, target_prefix="files")

        assert await self._files(message_id) == [f"{flow_id}/notes.txt"]

    async def test_a_path_storage_cannot_account_for_is_reported_and_left_alone(self, active_user, storage_dir, bucket):
        flow_id = await self._flow_with_attachment(storage_dir, active_user.id, "photo.png", b"png-bytes")
        elsewhere = f"/srv/old-host/{uuid.uuid4().hex}/gone.png"
        message_id = await self._message(flow_id, [elsewhere])

        results = await relocate_files(target_bucket=bucket, target_prefix="files")

        assert await self._files(message_id) == [elsewhere]
        failed = [r for r in results if r.status == "failed" and r.file_name == "gone.png"]
        assert len(failed) == 1
        assert str(message_id) in failed[0].reason
