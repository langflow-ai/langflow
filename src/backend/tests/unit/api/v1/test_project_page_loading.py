"""Project pagination must not fetch the discarded Folder.flows collection.

PostgreSQL route tests opt in with LANGFLOW_TEST_POSTGRES_URL and use only a
random temporary schema. The small app overrides authentication with a seeded
user; the full application's real authentication is covered by test_projects.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from fastapi_pagination import add_pagination
from httpx import ASGITransport, AsyncClient
from langflow.api.v1 import projects
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.authorization.base import ResourceVisibilityScope
from lfx.services.deps import injectable_session_scope
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(params=["sqlite", "postgres"])
async def project_store(request, tmp_path, client):  # noqa: ARG001
    """Initialize services normally, but isolate the route's database per test."""
    admin = None
    namespace = None
    if request.param == "postgres":
        raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not raw:
            pytest.skip("set LANGFLOW_TEST_POSTGRES_URL for real PostgreSQL coverage")
        pytest.importorskip("psycopg")
        url = sa.make_url(raw).set(drivername="postgresql+psycopg")
        admin = create_async_engine(url)
        namespace = f"project_page_{uuid4().hex}"
        async with admin.begin() as connection:
            await connection.execute(sa.schema.CreateSchema(namespace))
        engine = create_async_engine(url.update_query_dict({"options": f"-csearch_path={namespace}"}))
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/project-page.db")

        @sa.event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        owner = User(id=uuid4(), username=f"page-owner-{uuid4()}", password=uuid4().hex, is_active=True)
        other = User(id=uuid4(), username=f"page-other-{uuid4()}", password=uuid4().hex, is_active=True)
        folder = Folder(id=uuid4(), name="Page fixture", user_id=owner.id)
        foreign_folder = Folder(id=uuid4(), name="Foreign fixture", user_id=other.id)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        flows = [
            Flow(
                id=uuid4(),
                name=f"item_{index:02d}",
                user_id=owner.id,
                folder_id=folder.id,
                is_component=index % 2 == 1,
                updated_at=now + timedelta(seconds=index),
                data={"nodes": [], "edges": [], "padding": "x" * 100_000},
            )
            for index in range(25)
        ]
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all([owner, other])
            await session.flush()
            session.add_all([folder, foreign_folder])
            await session.flush()
            session.add_all(flows)
            await session.commit()

        async def database():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                yield session
                await session.commit()

        async def current_user():
            return owner

        app = FastAPI()
        app.include_router(projects.router, prefix="/api/v1")
        app.dependency_overrides[injectable_session_scope] = database
        app.dependency_overrides[get_current_active_user] = current_user
        add_pagination(app)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as route_client:
            yield engine, route_client, folder, foreign_folder, flows
    finally:
        await engine.dispose()
        if admin is not None:
            try:
                async with admin.begin() as connection:
                    await connection.execute(sa.schema.DropSchema(namespace, cascade=True))
            finally:
                await admin.dispose()


@contextmanager
def capture_statements(engine):
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    sa.event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        sa.event.remove(engine.sync_engine, "before_cursor_execute", record)


def relationship_reads(statements):
    return [statement for statement in statements if "flow.folder_id AS flow_folder_id" in statement]


@pytest.mark.parametrize(("page", "size"), [(1, 1), (2, 5), (6, 5), (1, 100)])
async def test_paginated_project_does_not_load_discarded_relationship(project_store, page, size):
    engine, client, folder, _foreign, flows = project_store
    with capture_statements(engine) as statements:
        response = await client.get(f"/api/v1/projects/{folder.id}", params={"page": page, "size": size})
    assert response.status_code == 200, response.text
    result = response.json()
    expected = list(reversed(flows))[(page - 1) * size : page * size]
    assert result["flows"]["total"] == 25
    assert [item["id"] for item in result["flows"]["items"]] == [str(flow.id) for flow in expected]
    assert [item["data"] for item in result["flows"]["items"]] == [flow.data for flow in expected]
    assert result["folder"]["id"] == str(folder.id)
    assert not relationship_reads(statements), statements
    assert len([sql for sql in statements if "FROM flow" in sql]) == 2
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)


@pytest.mark.parametrize("params", [{}, {"page": 2}, {"size": 5}])
async def test_nonpaginated_and_partial_project_keep_complete_flows(project_store, params):
    engine, client, folder, _foreign, flows = project_store
    with capture_statements(engine) as statements:
        response = await client.get(f"/api/v1/projects/{folder.id}", params=params)
    assert response.status_code == 200, response.text
    result = response.json()
    assert "folder" not in result
    assert {item["id"]: item["data"] for item in result["flows"]} == {str(flow.id): flow.data for flow in flows}
    assert len(relationship_reads(statements)) == 1


async def test_project_pages_match_full_response_and_filters(project_store):
    _engine, client, folder, _foreign, _flows = project_store
    full = (await client.get(f"/api/v1/projects/{folder.id}")).json()
    page = (await client.get(f"/api/v1/projects/{folder.id}", params={"page": 1, "size": 100})).json()
    assert {item["id"]: item for item in full.pop("flows")} == {item["id"]: item for item in page["flows"]["items"]}
    assert full == page["folder"]
    for flag in ["is_flow", "is_component"]:
        response = await client.get(
            f"/api/v1/projects/{folder.id}", params={"page": 1, "size": 100, flag: "true", "search": "item_0"}
        )
        assert response.status_code == 200, response.text
        result = response.json()["flows"]
        assert result["total"] == 5
        assert all(item["is_component"] == (flag == "is_component") for item in result["items"])


async def test_concurrent_project_reads_are_select_only_and_leave_rows_unchanged(project_store):
    engine, client, folder, _foreign, _flows = project_store
    url = f"/api/v1/projects/{folder.id}?page=2&size=5"
    async with AsyncSession(engine) as session:
        before = {row.id: row.model_dump() for row in (await session.exec(sa.select(Flow))).scalars()}
    expected = (await client.get(url)).json()
    with capture_statements(engine) as statements:
        responses = await asyncio.gather(*(client.get(url) for _ in range(4)))
    assert all(response.status_code == 200 and response.json() == expected for response in responses)
    assert not relationship_reads(statements)
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    async with AsyncSession(engine) as session:
        after = {row.id: row.model_dump() for row in (await session.exec(sa.select(Flow))).scalars()}
    assert before == after


async def test_foreign_missing_and_empty_project_pages(project_store):
    engine, client, folder, foreign, _flows = project_store
    for identity in [foreign.id, uuid4()]:
        response = await client.get(f"/api/v1/projects/{identity}?page=1&size=5")
        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found"}
    async with AsyncSession(engine) as session:
        await session.exec(sa.delete(Flow).where(Flow.folder_id == folder.id))
        await session.commit()
    response = await client.get(f"/api/v1/projects/{folder.id}?page=1&size=5")
    assert response.status_code == 200, response.text
    assert response.json()["flows"]["total"] == 0
    assert response.json()["flows"]["items"] == []


@pytest.mark.parametrize("paginated", [False, True])
@pytest.mark.parametrize("scope_mode", ["concrete", "fallback", "restricted"])
async def test_shared_scope_boundaries(project_store, monkeypatch, paginated, scope_mode):
    """Explicit auth boundary doubles exercise route branches, not plugin policy."""
    _engine, client, folder, _foreign, flows = project_store
    authz = AsyncMock()
    authz.supports_cross_user_fetch.return_value = True
    authz.is_enabled.return_value = True
    monkeypatch.setattr("langflow.services.deps.get_authorization_service", lambda: authz)
    monkeypatch.setattr(projects, "ensure_project_permission", AsyncMock())
    # For the restricted-key case, the project remains owned by the caller;
    # the other cases model a foreign project admitted by the project guard.
    if scope_mode != "restricted":
        async with AsyncSession(_engine) as session:
            stored = await session.get(Folder, folder.id)
            stored.user_id = None
            session.add(stored)
            await session.commit()
    monkeypatch.setattr(projects, "current_auth_is_restricted_api_key", lambda: scope_mode == "restricted")
    # Remove owner shortcuts for the flow scope assertion.
    async with AsyncSession(_engine) as session:
        await session.exec(sa.update(Flow).where(Flow.folder_id == folder.id).values(user_id=None))
        await session.commit()
    allowed = {flows[2].id, flows[8].id}
    scope = None if scope_mode == "fallback" else ResourceVisibilityScope(resource_ids=tuple(allowed))
    prefilter = AsyncMock(return_value=scope)
    monkeypatch.setattr(projects, "visible_scope_prefilter", prefilter)

    async def visible(_user, *, candidates, **_kwargs):
        return [flow for flow in candidates if flow.id in allowed]

    fallback = AsyncMock(side_effect=visible)
    monkeypatch.setattr(projects, "filter_visible_resources", fallback)
    params = {"page": 1, "size": 100} if paginated else {}
    response = await client.get(f"/api/v1/projects/{folder.id}", params=params)
    assert response.status_code == 200, response.text
    result = response.json()["flows"]
    rows = result["items"] if paginated else result
    assert {item["id"] for item in rows} == {str(identity) for identity in allowed}
    prefilter.assert_awaited_once()
    assert fallback.await_count == (1 if scope_mode == "fallback" else 0)
    if paginated:
        assert result["total"] == (25 if scope_mode == "fallback" else 2)


@pytest.mark.parametrize("paginated", [False, True])
async def test_project_denial_stays_not_found(project_store, monkeypatch, paginated):
    _engine, client, folder, _foreign, _flows = project_store
    monkeypatch.setattr(projects, "ensure_project_permission", AsyncMock(side_effect=HTTPException(403, "denied")))
    response = await client.get(f"/api/v1/projects/{folder.id}", params={"page": 1, "size": 5} if paginated else {})
    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


async def test_project_query_failure_is_sanitized(project_store):
    engine, client, folder, _foreign, _flows = project_store

    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "FROM folder" in statement:
            raise sa.exc.OperationalError(statement, {}, RuntimeError("private-database-detail"))

    sa.event.listen(engine.sync_engine, "before_cursor_execute", fail)
    try:
        response = await client.get(f"/api/v1/projects/{folder.id}?page=1&size=5")
    finally:
        sa.event.remove(engine.sync_engine, "before_cursor_execute", fail)
    assert response.status_code == 500
    assert response.json() == {"detail": projects.PROJECT_READ_FAILED}


async def test_escaped_search_and_legacy_null_component(project_store):
    engine, client, folder, _foreign, flows = project_store
    async with AsyncSession(engine) as session:
        await session.exec(sa.update(Flow).where(Flow.id == flows[0].id).values(name="literal_%", is_component=None))
        await session.commit()
    for params in [{}, {"page": 1, "size": 100}]:
        response = await client.get(f"/api/v1/projects/{folder.id}", params={**params, "search": "_%"})
        assert response.status_code == 200, response.text
        result = response.json()["flows"]
        rows = result["items"] if params else result
        if params:
            assert [item["id"] for item in rows] == [str(flows[0].id)]
        else:
            # Legacy nonpaginated reads ignore search; preserve that behavior.
            assert len(rows) == 25
        assert next(item for item in rows if item["id"] == str(flows[0].id))["is_component"] is None
