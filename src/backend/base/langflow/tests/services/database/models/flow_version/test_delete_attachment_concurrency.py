"""Exercise version deletion versus deployment attachment on real databases."""

import asyncio
import os
from contextlib import suppress
from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import (
    DeploymentProviderAccount,
    DeploymentProviderKey,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version import crud as version_crud
from langflow.services.database.models.flow_version.exceptions import FlowVersionDeployedError
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment import crud as attachment_crud
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    DeploymentAttachmentConflictError,
    create_deployment_attachment,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import FlowVersionDeploymentAttachment
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.adapters.deployment.schema import DeploymentType
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select, update
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def db_engine(request, tmp_path):
    if request.param == "sqlite":
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'versions.db'}", connect_args={"timeout": 0})

        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        try:
            async with engine.begin() as connection:
                await connection.run_sync(SQLModel.metadata.create_all)
            yield engine
        finally:
            await engine.dispose()
        return

    raw_url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not raw_url:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("PostgreSQL is required to exercise row locks")
    url = url.set(drivername="postgresql+psycopg")
    schema = f"version_delete_{uuid4().hex}"
    engine = create_async_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(SQLModel.metadata.create_all)
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest.fixture
async def version_and_deployment(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as db, db.begin():
        user = User(username="version-delete-test", password="unused")  # noqa: S106  # pragma: allowlist secret
        db.add(user)
        await db.flush()
        folder = Folder(name="project", user_id=user.id)
        account = DeploymentProviderAccount(
            user_id=user.id,
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            name="provider",
            provider_url="https://provider.example.com",
            api_key="unused",  # pragma: allowlist secret
        )
        db.add_all([folder, account])
        await db.flush()
        flow = Flow(name="flow", user_id=user.id, folder_id=folder.id)
        deployment = Deployment(
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=account.id,
            resource_key="deployment",
            deployment_type=DeploymentType.AGENT,
        )
        db.add_all([flow, deployment])
        await db.flush()
        version = FlowVersion(flow_id=flow.id, user_id=user.id, version_number=1, data={})
        db.add(version)
        await db.flush()
    return user.id, version.id, deployment.id


async def _wait_for_lock(engine, task, *, blocked_pid, blocker_pid):
    """Wait for PostgreSQL to report the competing transaction's actual lock wait."""

    async def wait():
        async with engine.connect() as connection:
            while not task.done():
                blockers = await connection.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": blocked_pid})
                if blocker_pid in blockers:
                    return
                await asyncio.sleep(0.01)
        pytest.fail("Competing operation completed before the first transaction released its lock")

    await asyncio.wait_for(wait(), timeout=10)


@pytest.mark.real_services
@pytest.mark.parametrize("db_engine", ["postgres"], indirect=True)
@pytest.mark.parametrize("reverse_order", [False, True], ids=["same-order", "opposite-order"])
async def test_concurrent_attachments_do_not_block_each_other(db_engine, version_and_deployment, reverse_order):
    """Different deployments can attach overlapping versions before either commits."""
    user_id, version_id, deployment_id = version_and_deployment
    async with AsyncSession(db_engine, expire_on_commit=False) as db, db.begin():
        version = await db.get(FlowVersion, version_id)
        deployment = await db.get(Deployment, deployment_id)
        other_version = FlowVersion(flow_id=version.flow_id, user_id=user_id, version_number=2, data={})
        other_deployment = Deployment(
            user_id=user_id,
            project_id=deployment.project_id,
            deployment_provider_account_id=deployment.deployment_provider_account_id,
            resource_key="other-deployment",
            deployment_type=DeploymentType.AGENT,
        )
        db.add_all([other_version, other_deployment])
        await db.flush()

    version_ids = [version_id, other_version.id]
    deployment_ids = [deployment_id, other_deployment.id]
    first_attached = [asyncio.Event(), asyncio.Event()]
    all_attached = [asyncio.Event(), asyncio.Event()]
    release_second = asyncio.Event()
    release_commit = asyncio.Event()

    async def attach_versions(index):
        ordered_ids = list(reversed(version_ids)) if index == 1 and reverse_order else version_ids
        async with AsyncSession(db_engine) as db, db.begin():
            for position, target_version_id in enumerate(ordered_ids):
                await create_deployment_attachment(
                    db,
                    user_id=user_id,
                    flow_version_id=target_version_id,
                    deployment_id=deployment_ids[index],
                    provider_snapshot_id=f"snapshot-{target_version_id}",
                )
                if position == 0:
                    first_attached[index].set()
                    await asyncio.wait_for(release_second.wait(), timeout=10)
            all_attached[index].set()
            await asyncio.wait_for(release_commit.wait(), timeout=10)

    async def release_when_attached():
        await asyncio.wait_for(asyncio.gather(*(ready.wait() for ready in first_attached)), timeout=10)
        release_second.set()
        await asyncio.wait_for(asyncio.gather(*(ready.wait() for ready in all_attached)), timeout=10)
        release_commit.set()

    tasks = [asyncio.create_task(attach_versions(index)) for index in range(2)]
    tasks.append(asyncio.create_task(release_when_attached()))
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
    finally:
        release_second.set()
        release_commit.set()
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

    async with AsyncSession(db_engine) as db:
        attachments = (
            await db.exec(
                select(
                    FlowVersionDeploymentAttachment.flow_version_id,
                    FlowVersionDeploymentAttachment.deployment_id,
                )
            )
        ).all()
        assert set(attachments) == {
            (target_version_id, target_deployment_id)
            for target_version_id in version_ids
            for target_deployment_id in deployment_ids
        }


@pytest.mark.real_services
@pytest.mark.parametrize("db_engine", ["postgres"], indirect=True)
@pytest.mark.parametrize("first_operation", ["attachment", "delete"])
async def test_delete_and_attachment_are_serialized(db_engine, version_and_deployment, monkeypatch, first_operation):
    user_id, version_id, deployment_id = version_and_deployment
    first_ready = asyncio.Event()
    release_first = asyncio.Event()
    second_ready = asyncio.Event()
    pids = {}

    async def attach(db):
        await create_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=version_id,
            deployment_id=deployment_id,
            provider_snapshot_id="snapshot",
        )

    async def delete(db):
        await version_crud.delete_flow_version_entry(db, version_id, user_id)

    if first_operation == "delete":
        original_guard = version_crud.has_deployment_attachments

        async def pause_after_guard(*args, **kwargs):
            attached = await original_guard(*args, **kwargs)
            first_ready.set()
            await asyncio.wait_for(release_first.wait(), timeout=10)
            return attached

        monkeypatch.setattr(version_crud, "has_deployment_attachments", pause_after_guard)

    async def run_first():
        async with AsyncSession(db_engine) as db, db.begin():
            pids["first"] = await db.scalar(text("SELECT pg_backend_pid()"))
            if first_operation == "attachment":
                await attach(db)
                first_ready.set()
                await asyncio.wait_for(release_first.wait(), timeout=10)
            else:
                await delete(db)

    async def run_second():
        await asyncio.wait_for(first_ready.wait(), timeout=10)
        async with AsyncSession(db_engine) as db, db.begin():
            pids["second"] = await db.scalar(text("SELECT pg_backend_pid()"))
            second_ready.set()
            await (delete(db) if first_operation == "attachment" else attach(db))

    first = asyncio.create_task(run_first())
    second = asyncio.create_task(run_second())
    try:
        await asyncio.wait_for(second_ready.wait(), timeout=10)
        await _wait_for_lock(db_engine, second, blocked_pid=pids["second"], blocker_pid=pids["first"])
        release_first.set()
        await asyncio.wait_for(first, timeout=10)
        expected_error = (
            FlowVersionDeployedError if first_operation == "attachment" else DeploymentAttachmentConflictError
        )
        with pytest.raises(expected_error):
            await asyncio.wait_for(second, timeout=10)
    finally:
        release_first.set()
        for task in (first, second):
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

    async with AsyncSession(db_engine) as db:
        version = (await db.exec(select(FlowVersion.id).where(FlowVersion.id == version_id))).first()
        attachments = (
            await db.exec(
                select(FlowVersionDeploymentAttachment.flow_version_id).where(
                    FlowVersionDeploymentAttachment.flow_version_id == version_id
                )
            )
        ).all()
        assert version == (version_id if first_operation == "attachment" else None)
        assert attachments == ([version_id] if first_operation == "attachment" else [])


@pytest.mark.parametrize("db_engine", ["sqlite"], indirect=True)
@pytest.mark.parametrize("operation", ["attachment", "delete"])
async def test_sqlite_locks_before_guard_until_commit(db_engine, version_and_deployment, monkeypatch, operation):
    user_id, version_id, deployment_id = version_and_deployment

    async def competing_write():
        async with AsyncSession(db_engine) as db, db.begin():
            await db.exec(update(FlowVersion).where(FlowVersion.id == version_id).values(id=FlowVersion.id))

    module = version_crud if operation == "delete" else attachment_crud
    guard_name = "has_deployment_attachments" if operation == "delete" else "ensure_attachment_project_match"
    original_guard = getattr(module, guard_name)
    guard_checked = False

    async def check_lock_before_guard(*args, **kwargs):
        nonlocal guard_checked
        with pytest.raises(OperationalError, match="database is locked"):
            await competing_write()
        guard_checked = True
        return await original_guard(*args, **kwargs)

    monkeypatch.setattr(module, guard_name, check_lock_before_guard)
    async with AsyncSession(db_engine) as db, db.begin():
        if operation == "delete":
            await version_crud.delete_flow_version_entry(db, version_id, user_id)
        else:
            await create_deployment_attachment(
                db,
                user_id=user_id,
                flow_version_id=version_id,
                deployment_id=deployment_id,
                provider_snapshot_id="snapshot",
            )
        assert guard_checked
        with pytest.raises(OperationalError, match="database is locked"):
            await competing_write()
    # The helper must retain the lock until its caller commits, then release it.
    await competing_write()
