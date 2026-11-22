"""Header-only list reads must not hydrate discarded ordinary-flow JSON.

The small ASGI app uses the real session_scope commit/rollback dependency.
PostgreSQL opts in with LANGFLOW_TEST_POSTGRES_URL and a random isolated schema.
Authentication integration is covered by test_flows and the RBAC route tests.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from httpx import ASGITransport, AsyncClient
from langflow.api.v1 import flows as routes
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow, FlowType
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from lfx.services import deps
from lfx.services.authorization.base import ResourceVisibilityScope
from lfx.services.authorization.service import AuthorizationService
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


class HeaderAuthorization(AuthorizationService):
    """Exercise the real listing adapter through its resource-ID plugin API."""

    SUPPORTS_API_KEY_SCOPES = True

    def __init__(self):
        super().__init__()
        self.scope = None
        self.allowed = set()
        self.requests = []
        self.fail = False

    async def get_resource_visibility(self, **kwargs):  # noqa: ARG002
        return self.scope

    async def batch_enforce(self, *, requests, **kwargs):
        self.requests.append((requests, kwargs))
        if self.fail:
            message = "private authorization failure"
            raise RuntimeError(message)
        return [obj in self.allowed for obj, _act in requests]


@pytest.fixture(params=["sqlite", "postgres"])
async def header_store(request, tmp_path, client, monkeypatch):  # noqa: ARG001
    admin = None
    namespace = None
    if request.param == "postgres":
        raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not raw:
            pytest.skip("set LANGFLOW_TEST_POSTGRES_URL for real PostgreSQL coverage")
        pytest.importorskip("psycopg")
        url = sa.make_url(raw).set(drivername="postgresql+psycopg")
        admin = create_async_engine(url)
        namespace = f"flow_header_{uuid4().hex}"
        async with admin.begin() as connection:
            await connection.execute(sa.schema.CreateSchema(namespace))
        engine = create_async_engine(url.update_query_dict({"options": f"-csearch_path={namespace}"}))
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/headers.db")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        owner = User(id=uuid4(), username=f"header-owner-{uuid4()}", password=uuid4().hex, is_active=True)
        other = User(id=uuid4(), username=f"header-other-{uuid4()}", password=uuid4().hex, is_active=True)
        workspace = uuid4()
        folder = Folder(id=uuid4(), name=routes.DEFAULT_FOLDER_NAME, user_id=owner.id, workspace_id=workspace)
        starter = Folder(id=uuid4(), name=routes.STARTER_FOLDER_NAME)
        secret = {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {"name": "api_key", "password": True, "value": "fixture-only"},
                            }
                        }
                    }
                }
            ],
            "edges": [],
        }
        data = {
            "ordinary": {"nodes": [{}], "edges": [], "is_component": True, "padding": "x" * 100_000},
            "component": secret,
            "legacy_one": {"nodes": [{}], "edges": []},
            "legacy_many": {"nodes": [{}, {}], "edges": []},
            "legacy_true": {"nodes": [], "edges": [], "is_component": True},
            "legacy_false": {"nodes": [{}], "edges": [], "is_component": False},
            "legacy_empty": {},
            "legacy_json_null": None,
            "legacy_sql_null": None,
            "foreign_component": secret,
            "null_owner": {"nodes": [{}, {}], "edges": []},
            "example": {"nodes": [{}, {}], "edges": []},
        }
        rows = {}
        for name, payload in data.items():
            rows[name] = Flow(
                id=uuid4(),
                name=name,
                data=payload,
                user_id=other.id if name == "foreign_component" else None if name == "null_owner" else owner.id,
                folder_id=starter.id if name == "example" else folder.id,
                is_component=name in {"component", "foreign_component"},
                flow_type=FlowType.AGENT if name == "ordinary" else FlowType.WORKFLOW,
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all([owner, other])
            await session.flush()
            session.add_all([folder, starter])
            await session.flush()
            session.add_all(list(rows.values()))
            await session.flush()
            await session.exec(sa.update(Flow).where(Flow.name.like("legacy_%")).values(is_component=None))
            await session.exec(sa.update(Flow).where(Flow.id == rows["legacy_sql_null"].id).values(data=sa.null()))
            await session.commit()

        closed = []

        @asynccontextmanager
        async def with_session():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                yield session
            # Mark completion only after AsyncSession.__aexit__ closes the session.
            closed.append(session)

        # Keep the production session_scope, including its commit and rollback.
        monkeypatch.setattr(deps, "get_db_service", lambda: SimpleNamespace(_with_session=with_session))
        settings = get_settings_service()
        monkeypatch.setattr(settings.auth_settings, "AUTO_LOGIN", False)
        monkeypatch.setattr(settings.auth_settings, "AUTHZ_ENABLED", True)
        monkeypatch.setattr(settings.auth_settings, "AUTHZ_SUPERUSER_BYPASS", False)
        authz = HeaderAuthorization()
        manager = get_service_manager()
        monkeypatch.setitem(manager.services, ServiceType.AUTHORIZATION_SERVICE, authz)

        async def current_user():
            return owner

        app = FastAPI()
        app.include_router(routes.router, prefix="/api/v1")
        app.dependency_overrides[get_current_active_user] = current_user
        add_pagination(app)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield SimpleNamespace(
                engine=engine,
                http=http,
                rows=rows,
                folder=folder,
                starter=starter,
                owner=owner,
                other=other,
                data=data,
                authz=authz,
                closed=closed,
                settings=settings,
            )
    finally:
        await engine.dispose()
        if admin is not None:
            try:
                async with admin.begin() as connection:
                    await connection.execute(sa.schema.DropSchema(namespace, cascade=True))
            finally:
                await admin.dispose()


@contextmanager
def capture_loads(engine):
    statements = []
    loaded = {}

    def sql(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    def load(flow, _context):
        loaded[flow.name] = (flow.is_component, flow.data)

    sa.event.listen(engine.sync_engine, "before_cursor_execute", sql)
    sa.event.listen(Flow, "load", load)
    try:
        yield statements, loaded
    finally:
        sa.event.remove(engine.sync_engine, "before_cursor_execute", sql)
        sa.event.remove(Flow, "load", load)


def headers_by_name(response):
    assert response.status_code == 200, response.text
    return {item["name"]: item for item in response.json()}


async def test_get_all_headers_do_not_hydrate_ordinary_data(header_store):
    store = header_store
    with capture_loads(store.engine) as (sql, loaded):
        result = headers_by_name(await store.http.get("/api/v1/flows/", params={"header_flows": True}))
    assert result["ordinary"]["data"] is None
    assert loaded["ordinary"] == (False, None)
    assert loaded["component"][1] == store.data["component"]
    assert loaded["legacy_one"] == (None, store.data["legacy_one"])
    assert result["legacy_one"]["is_component"] is True
    assert result["legacy_many"]["is_component"] is False
    assert result["legacy_true"]["is_component"] is True
    assert result["legacy_false"]["is_component"] is False
    for name in ["legacy_empty", "legacy_json_null", "legacy_sql_null"]:
        assert result[name]["is_component"] is None
        assert result[name]["data"] is None
    assert "foreign_component" not in result
    assert "null_owner" not in result
    selects = [statement for statement in sql if statement.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 3, sql
    assert "CASE WHEN" in selects[-1]
    assert "ELSE flow.data END" in selects[-1]
    assert store.closed
    async with AsyncSession(store.engine) as session:
        stored = {flow.name: flow for flow in (await session.exec(select(Flow))).all()}
        assert stored["ordinary"].data == store.data["ordinary"]
        assert stored["legacy_one"].is_component is True
        assert stored["legacy_many"].is_component is False
        assert stored["component"].data == store.data["component"]


@pytest.mark.parametrize("scope_mode", ["fallback", "empty", "resource", "workspace"])
async def test_header_projection_preserves_authorization_and_secrets(header_store, scope_mode):
    store = header_store
    foreign = store.rows["foreign_component"]
    if scope_mode == "empty":
        store.authz.scope = ResourceVisibilityScope()
    elif scope_mode == "resource":
        store.authz.scope = ResourceVisibilityScope(resource_ids=(foreign.id,))
    elif scope_mode == "workspace":
        store.authz.scope = ResourceVisibilityScope(workspace_ids=(store.folder.workspace_id,))
    with capture_loads(store.engine) as (sql, loaded):
        result = headers_by_name(await store.http.get("/api/v1/flows/", params={"header_flows": True}))
    assert result["ordinary"]["data"] is None
    assert loaded["ordinary"] == (False, None)
    if scope_mode in {"resource", "workspace"}:
        template = result["foreign_component"]["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["api_key"]["value"] is None
    else:
        assert "foreign_component" not in result
    assert result["component"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "fixture-only"
    assert len([statement for statement in sql if statement.lstrip().upper().startswith("SELECT")]) == 3
    # The prefilter is authoritative, and owned fallback rows bypass enforce.
    assert not store.authz.requests
    async with AsyncSession(store.engine) as session:
        persisted = await session.get(Flow, foreign.id)
        assert persisted.data == store.data["foreign_component"]


@pytest.mark.parametrize("allowed", [False, True])
async def test_auto_login_null_owner_keeps_real_batch_filter(header_store, allowed):
    store = header_store
    store.settings.auth_settings.AUTO_LOGIN = True
    null_owner = store.rows["null_owner"]
    if allowed:
        store.authz.allowed.add(f"flow:{null_owner.id}")
    result = headers_by_name(await store.http.get("/api/v1/flows/", params={"header_flows": True}))
    assert ("null_owner" in result) is allowed
    assert "foreign_component" not in result
    assert store.authz.requests
    for requests, kwargs in store.authz.requests:
        assert requests == [(f"flow:{null_owner.id}", "read")]
        assert kwargs["user_id"] == store.owner.id
        assert isinstance(kwargs["domain"], str)
        assert all(isinstance(obj, str) for obj, _act in requests)


@pytest.mark.parametrize(("get_all", "header"), [(True, False), (False, False), (False, True)])
async def test_other_listing_modes_do_not_project_data(header_store, get_all, header):
    store = header_store
    with capture_loads(store.engine) as (sql, loaded):
        response = await store.http.get(
            "/api/v1/flows/",
            params={
                "get_all": get_all,
                "header_flows": header,
                "folder_id": str(store.folder.id),
                "size": 50,
            },
        )
    assert response.status_code == 200, response.text
    rows = response.json() if get_all else response.json()["items"]
    result = {item["name"]: item for item in rows}
    assert loaded["ordinary"][1] == store.data["ordinary"]
    assert not any("ELSE flow.data END" in statement for statement in sql)
    assert result["ordinary"]["data"] == (None if header else store.data["ordinary"])
    if not get_all:
        assert response.json()["total"] == 9
        if header:
            assert result["legacy_one"]["is_component"] is None
            assert result["legacy_one"]["data"] is None


@pytest.mark.parametrize(
    ("params", "names"),
    [
        ({"components_only": True}, {"component"}),
        ({"flow_type": "agent"}, {"ordinary"}),
        ({"flow_type": "agent", "components_only": True}, set()),
        ({"flow_type": "agent", "remove_example_flows": True}, {"ordinary"}),
    ],
)
async def test_header_filters_keep_their_existing_predicates(header_store, params, names):
    result = headers_by_name(
        await header_store.http.get(
            "/api/v1/flows/",
            params={"header_flows": True, **params},
        )
    )
    assert set(result) == names


async def test_header_payload_matches_unprojected_same_engine_baseline(header_store, monkeypatch):
    store = header_store
    store.authz.scope = ResourceVisibilityScope(resource_ids=(store.rows["foreign_component"].id,))
    # Replace only this query option to exercise the old full-column SELECT;
    # the real handler, session lifecycle and authorization path stay unchanged.
    with monkeypatch.context() as patch:
        patch.setattr(routes, "with_expression", lambda _column, _expression: sa.orm.undefer(Flow.data))
        baseline = headers_by_name(await store.http.get("/api/v1/flows/", params={"header_flows": True}))
    with capture_loads(store.engine) as (sql, loaded):
        candidate = headers_by_name(await store.http.get("/api/v1/flows/", params={"header_flows": True}))
    assert candidate == baseline
    assert candidate["ordinary"]["updated_at"] == "2026-01-01T00:00:00+00:00"
    assert loaded["ordinary"][1] is None
    assert len([statement for statement in sql if statement.lstrip().upper().startswith("SELECT")]) == 3


async def test_projected_request_does_not_change_data_on_later_metadata_write(header_store):
    store = header_store
    response = await store.http.get("/api/v1/flows/", params={"header_flows": True})
    assert response.status_code == 200
    async with AsyncSession(store.engine, expire_on_commit=False) as session:
        row = await session.get(Flow, store.rows["ordinary"].id)
        assert row.data == store.data["ordinary"]
        row.name = "renamed ordinary"
        await session.commit()
    async with AsyncSession(store.engine) as session:
        row = await session.get(Flow, store.rows["ordinary"].id)
        assert row.data == store.data["ordinary"]
        assert row.name == "renamed ordinary"


async def test_header_sql_failure_rolls_back_and_next_request_succeeds(header_store):
    store = header_store

    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "FROM flow" in statement:
            message = "private database details"
            raise RuntimeError(message)

    sa.event.listen(store.engine.sync_engine, "before_cursor_execute", fail)
    try:
        response = await store.http.get("/api/v1/flows/", params={"header_flows": True})
    finally:
        sa.event.remove(store.engine.sync_engine, "before_cursor_execute", fail)
    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred while listing flows."}
    async with AsyncSession(store.engine) as session:
        row = await session.get(Flow, store.rows["legacy_one"].id)
        assert row.is_component is None
    assert (await store.http.get("/api/v1/flows/", params={"header_flows": True})).status_code == 200


async def test_header_authorization_failure_rolls_back_legacy_inference(header_store):
    store = header_store
    store.settings.auth_settings.AUTO_LOGIN = True
    store.authz.fail = True
    response = await store.http.get("/api/v1/flows/", params={"header_flows": True})
    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred while listing flows."}
    async with AsyncSession(store.engine) as session:
        row = await session.get(Flow, store.rows["legacy_one"].id)
        assert row.is_component is None
        assert row.data == store.data["legacy_one"]
    store.authz.fail = False
    assert (await store.http.get("/api/v1/flows/", params={"header_flows": True})).status_code == 200


@pytest.mark.parametrize(("page", "size", "count"), [(1, 1, 1), (2, 5, 4), (3, 5, 0)])
async def test_paginated_headers_keep_page_membership_and_total(header_store, page, size, count):
    store = header_store
    params = {"get_all": False, "folder_id": str(store.folder.id), "page": page, "size": size}
    baseline = await store.http.get("/api/v1/flows/", params=params)
    # Full reads reject legacy empty data only if the schema requires it; the
    # seeded values are deliberately valid for the existing full-read contract.
    assert baseline.status_code == 200, baseline.text
    with capture_loads(store.engine) as (sql, _loaded):
        candidate = await store.http.get("/api/v1/flows/", params={**params, "header_flows": True})
    assert candidate.status_code == 200, candidate.text
    assert candidate.json()["total"] == baseline.json()["total"] == 9
    assert len(candidate.json()["items"]) == count
    assert [row["id"] for row in candidate.json()["items"]] == [row["id"] for row in baseline.json()["items"]]
    assert not any("ELSE flow.data END" in statement for statement in sql)


async def test_header_sql_count_does_not_grow_with_ordinary_rows(header_store):
    store = header_store
    async with AsyncSession(store.engine) as session:
        session.add_all(
            [
                Flow(
                    name=f"bulk-{index}",
                    user_id=store.owner.id,
                    folder_id=store.folder.id,
                    is_component=False,
                    data={"nodes": [], "edges": [], "padding": "x" * 10_000},
                )
                for index in range(50)
            ]
        )
        await session.commit()
    with capture_loads(store.engine) as (sql, loaded):
        result = headers_by_name(await store.http.get("/api/v1/flows/", params={"header_flows": True}))
    assert len(result) == 60
    assert all(loaded[f"bulk-{index}"] == (False, None) for index in range(50))
    assert len([statement for statement in sql if statement.lstrip().upper().startswith("SELECT")]) == 3


async def test_header_projection_is_session_local_and_does_not_dirty_data(header_store):
    store = header_store
    option = routes.with_expression(
        Flow.data,
        sa.case((Flow.is_component.is_(False), sa.null()), else_=Flow.data),
    )
    statement = select(Flow).where(Flow.id == store.rows["ordinary"].id)
    async with AsyncSession(store.engine, expire_on_commit=False) as session:
        projected = (await session.exec(statement.options(option))).one()
        assert projected.data is None
        assert not sa.inspect(projected).attrs.data.history.has_changes()
        projected.name = "metadata changed"
        await session.commit()
        assert (await session.exec(statement)).one().data is None
        await session.refresh(projected)
        assert projected.data is None  # The header-only option is sticky within this identity map.
    async with AsyncSession(store.engine) as session:
        complete = await session.get(Flow, store.rows["ordinary"].id)
        assert complete.data == store.data["ordinary"]
        assert complete.name == "metadata changed"


async def test_header_projection_preserves_preloaded_full_identity(header_store):
    store = header_store
    statement = select(Flow).where(Flow.id == store.rows["ordinary"].id)
    option = routes.with_expression(
        Flow.data,
        sa.case((Flow.is_component.is_(False), sa.null()), else_=Flow.data),
    )
    async with AsyncSession(store.engine, expire_on_commit=False) as session:
        complete = (await session.exec(statement)).one()
        assert complete.data == store.data["ordinary"]
        with capture_loads(store.engine) as (sql, loaded):
            preloaded = (await session.exec(statement.options(option))).one()
        assert preloaded is complete
        assert preloaded.data == store.data["ordinary"]  # Existing full rows do not gain the saving.
        assert not loaded  # The identity map reused the full object rather than loading a new one.
        assert not sa.inspect(preloaded).attrs.data.history.has_changes()
        assert any("ELSE flow.data END" in query for query in sql)
        await session.commit()
    async with AsyncSession(store.engine) as session:
        persisted = await session.get(Flow, store.rows["ordinary"].id)
        assert persisted.data == store.data["ordinary"]
