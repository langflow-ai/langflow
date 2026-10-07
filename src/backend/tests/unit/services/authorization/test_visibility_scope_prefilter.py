"""Structured DB prefilter coverage for scoped authorization grants."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.authorization.listing import (
    resource_visible_in_scope,
    restrict_to_owned_or_visible_scope,
    visible_scope_prefilter,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from lfx.services.adapters.deployment.schema import DeploymentType
from lfx.services.authorization.base import ResourceVisibilityScope
from sqlmodel import select

from ._common import _StubAuthorizationService, install_authz, install_settings


class _ScopedAuthorizationService(_StubAuthorizationService):
    def __init__(self, scope: ResourceVisibilityScope | None) -> None:
        super().__init__()
        self.scope = scope

    async def get_resource_visibility(self, **kwargs) -> ResourceVisibilityScope | None:
        self.visible_calls.append(kwargs)
        return self.scope


@pytest.mark.anyio
async def test_visible_scope_prefilter_forwards_structured_scope(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    workspace_id = uuid4()
    project_id = uuid4()
    scope = ResourceVisibilityScope(workspace_ids=(workspace_id,), project_ids=(project_id,))
    service = _ScopedAuthorizationService(scope)
    install_authz(monkeypatch, service)

    result = await visible_scope_prefilter(fake_user, resource_type="flow", act="read")

    assert result == scope
    assert service.visible_calls == [
        {
            "user_id": fake_user.id,
            "resource_type": "flow",
            "domain": "*",
            "act": "read",
            "context": {"is_superuser": False},
        }
    ]


@pytest.mark.anyio
async def test_visible_scope_prefilter_adapts_legacy_concrete_id_service(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    visible_ids = [uuid4(), uuid4()]
    service = _StubAuthorizationService(visible_ids=visible_ids)
    install_authz(monkeypatch, service)

    result = await visible_scope_prefilter(fake_user, resource_type="flow", act="read")

    assert result == ResourceVisibilityScope(resource_ids=tuple(visible_ids))
    assert len(service.visible_calls) == 1


def test_scope_predicate_unions_owner_explicit_workspace_and_project_grants():
    owner_id = uuid4()
    scope = ResourceVisibilityScope(
        resource_ids=(uuid4(),),
        workspace_ids=(uuid4(),),
        project_ids=(uuid4(),),
    )

    constrained = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == owner_id,
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=scope,
    )

    sql = str(constrained)
    assert "flow.user_id =" in sql
    assert "flow.id IN" in sql
    assert "flow.workspace_id IN" in sql
    assert "flow.folder_id IN" in sql
    assert sql.count(" OR ") == 3


def test_global_scope_does_not_emit_an_unbounded_id_list():
    constrained = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == uuid4(),
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=ResourceVisibilityScope(all_resources=True),
    )

    sql = str(constrained)
    assert "flow.id IN" not in sql
    assert "flow.user_id =" not in sql


async def test_global_scope_excludes_reserved_projects_but_keeps_owner_share_and_folderless(async_session):
    owner_id = uuid4()
    other_owner_id = uuid4()
    ordinary_project_id = uuid4()
    excluded_project_id = uuid4()
    ordinary_flow = Flow(name="ordinary", user_id=other_owner_id, folder_id=ordinary_project_id)
    excluded_flow = Flow(name="excluded", user_id=other_owner_id, folder_id=excluded_project_id)
    owned_excluded_flow = Flow(name="owned excluded", user_id=owner_id, folder_id=excluded_project_id)
    shared_excluded_flow = Flow(name="shared excluded", user_id=other_owner_id, folder_id=excluded_project_id)
    folderless_flow = Flow(name="folderless", user_id=other_owner_id, folder_id=None)
    async_session.add_all(
        [
            Folder(id=ordinary_project_id, name="Ordinary project"),
            Folder(id=excluded_project_id, name="Reserved project"),
            ordinary_flow,
            excluded_flow,
            owned_excluded_flow,
            shared_excluded_flow,
            folderless_flow,
        ]
    )
    await async_session.commit()

    scope = ResourceVisibilityScope(
        all_resources=True,
        resource_ids=(shared_excluded_flow.id,),
        excluded_global_project_ids=(excluded_project_id,),
    )
    stmt = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == owner_id,
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=scope,
    )
    rows = list((await async_session.exec(stmt)).all())

    assert {row.id for row in rows} == {
        ordinary_flow.id,
        owned_excluded_flow.id,
        shared_excluded_flow.id,
        folderless_flow.id,
    }
    assert resource_visible_in_scope(
        resource_id=ordinary_flow.id,
        project_id=ordinary_project_id,
        visibility=scope,
    )
    assert not resource_visible_in_scope(
        resource_id=excluded_flow.id,
        project_id=excluded_project_id,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=shared_excluded_flow.id,
        project_id=excluded_project_id,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=folderless_flow.id,
        project_id=None,
        visibility=scope,
    )


def test_unassigned_workspace_scope_uses_a_compact_null_predicate():
    excluded_project_id = uuid4()
    scope = ResourceVisibilityScope(
        include_unassigned_workspace=True,
        excluded_workspace_project_ids=(excluded_project_id,),
    )
    constrained = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == uuid4(),
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=scope,
    )

    sql = str(constrained)
    assert "flow.workspace_id IS NULL" in sql
    assert "flow.folder_id IS NOT NULL" in sql
    assert "flow.folder_id NOT IN" in sql
    assert not resource_visible_in_scope(
        resource_id=uuid4(),
        workspace_id=None,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=uuid4(),
        workspace_id=None,
        project_id=uuid4(),
        visibility=scope,
    )
    assert not resource_visible_in_scope(
        resource_id=uuid4(),
        workspace_id=uuid4(),
        visibility=scope,
    )
    assert not resource_visible_in_scope(
        resource_id=uuid4(),
        workspace_id=None,
        project_id=excluded_project_id,
        visibility=scope,
    )


async def test_workspace_scope_sql_matches_in_memory_for_project_nulls_and_exclusions(async_session):
    owner_id = uuid4()
    ordinary_project_id = uuid4()
    excluded_project_id = uuid4()
    explicit_workspace_id = uuid4()
    ordinary_default_flow = Flow(name="ordinary default", folder_id=ordinary_project_id, workspace_id=None)
    excluded_default_flow = Flow(name="excluded default", folder_id=excluded_project_id, workspace_id=None)
    folderless_default_flow = Flow(name="folderless default", folder_id=None, workspace_id=None)
    explicit_workspace_flow = Flow(name="workspace only", folder_id=None, workspace_id=explicit_workspace_id)
    excluded_explicit_flow = Flow(
        name="excluded explicit",
        folder_id=excluded_project_id,
        workspace_id=explicit_workspace_id,
    )
    async_session.add_all(
        [
            Folder(id=ordinary_project_id, name="Ordinary project"),
            Folder(id=excluded_project_id, name="Reserved project", workspace_id=explicit_workspace_id),
            ordinary_default_flow,
            excluded_default_flow,
            folderless_default_flow,
            explicit_workspace_flow,
            excluded_explicit_flow,
        ]
    )
    await async_session.commit()

    default_scope = ResourceVisibilityScope(
        include_unassigned_workspace=True,
        excluded_workspace_project_ids=(excluded_project_id,),
    )
    default_stmt = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == owner_id,
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=default_scope,
    )
    default_rows = list((await async_session.exec(default_stmt)).all())
    assert [row.id for row in default_rows] == [ordinary_default_flow.id]

    explicit_scope = ResourceVisibilityScope(
        workspace_ids=(explicit_workspace_id,),
        excluded_workspace_project_ids=(excluded_project_id,),
    )
    explicit_stmt = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == owner_id,
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=explicit_scope,
    )
    explicit_rows = list((await async_session.exec(explicit_stmt)).all())
    assert [row.id for row in explicit_rows] == [explicit_workspace_flow.id]

    cases = [
        (ordinary_default_flow, default_scope, True),
        (excluded_default_flow, default_scope, False),
        (folderless_default_flow, default_scope, False),
        (explicit_workspace_flow, explicit_scope, True),
        (excluded_explicit_flow, explicit_scope, False),
    ]
    for flow, scope, expected in cases:
        assert (
            resource_visible_in_scope(
                resource_id=flow.id,
                workspace_id=flow.workspace_id,
                project_id=flow.folder_id,
                visibility=scope,
            )
            is expected
        )


def test_scope_reports_cross_user_access_without_resource_enumeration():
    assert ResourceVisibilityScope().has_cross_user_access is False
    assert ResourceVisibilityScope(all_resources=True).has_cross_user_access is True
    assert ResourceVisibilityScope(workspace_ids=(uuid4(),)).has_cross_user_access is True
    assert ResourceVisibilityScope(include_unassigned_workspace=True).has_cross_user_access is True


@pytest.mark.parametrize("resource_type", ["project", "flow", "deployment"])
@pytest.mark.parametrize("broad_scope", ["global", "workspace", "unassigned"])
async def test_personal_project_exclusion_preserves_additive_grants_and_pagination(
    async_session, resource_type, broad_scope
):
    owner_id, other_owner_id = uuid4(), uuid4()
    workspace_id = uuid4() if broad_scope == "workspace" else None
    projects = [
        Folder(name=name, user_id=other_owner_id, workspace_id=workspace_id, is_personal=personal)
        for name, personal in (
            ("Ordinary", False),
            ("Hidden personal", True),
            ("Owned personal", True),
            ("Shared personal", True),
            ("Delegated personal", True),
            ("Reserved", False),
        )
    ]
    projects[2].user_id = owner_id
    model, project_column = {
        "project": (Folder, Folder.id),
        "flow": (Flow, Flow.folder_id),
        "deployment": (Deployment, Deployment.project_id),
    }[resource_type]
    resources = []
    for project in projects:
        if resource_type == "project":
            resource = project
        elif resource_type == "flow":
            resource = Flow(name=project.name, user_id=project.user_id, folder_id=project.id, workspace_id=workspace_id)
        else:
            resource = Deployment(
                resource_key=str(uuid4()),
                display_name=project.name,
                user_id=project.user_id,
                project_id=project.id,
                workspace_id=workspace_id,
                deployment_provider_account_id=uuid4(),
                deployment_type=DeploymentType.AGENT,
            )
        resources.append(resource)
    ids = [resource.id for resource in resources]
    project_ids = [project.id for project in projects]
    scope = ResourceVisibilityScope(
        all_resources=broad_scope == "global",
        workspace_ids=(workspace_id,) if workspace_id else (),
        include_unassigned_workspace=broad_scope == "unassigned",
        project_ids=(project_ids[4],),
        resource_ids=(ids[3],),
        excluded_global_project_ids=(project_ids[5],),
        excluded_workspace_project_ids=(project_ids[5],),
        exclude_personal_projects=True,
    )
    async_session.add_all(projects)
    if resource_type != "project":
        async_session.add_all(resources)
    await async_session.commit()
    stmt = restrict_to_owned_or_visible_scope(
        select(model.id),
        id_column=model.id,
        owner_clause=model.user_id == owner_id,
        workspace_column=model.workspace_id,
        project_column=project_column,
        visibility=scope,
    )
    expected = {ids[0], ids[2], ids[3], ids[4]}
    assert set((await async_session.exec(stmt)).all()) == expected
    assert (
        list((await async_session.exec(stmt.order_by(model.id).offset(1).limit(2))).all())
        == sorted(expected, key=lambda value: value.hex)[1:3]
    )
    for index in (0, 1, 3, 4, 5):
        assert resource_visible_in_scope(
            resource_id=ids[index],
            project_id=project_ids[index],
            workspace_id=workspace_id,
            project_is_personal=index in {1, 3, 4},
            visibility=scope,
        ) is (ids[index] in expected)


@pytest.mark.parametrize("broad_scope", ["global", "workspace", "unassigned"])
def test_personal_exclusions_require_metadata_but_keep_explicit_grants(broad_scope):
    resource_id, shared_id, project_id, delegated_id, workspace_id = [uuid4() for _ in range(5)]
    scope = ResourceVisibilityScope(
        all_resources=broad_scope == "global",
        workspace_ids=(workspace_id,) if broad_scope == "workspace" else (),
        include_unassigned_workspace=broad_scope == "unassigned",
        resource_ids=(shared_id,),
        project_ids=(delegated_id,),
        exclude_personal_projects=True,
    )
    workspace = workspace_id if broad_scope == "workspace" else None
    assert not resource_visible_in_scope(
        resource_id=resource_id,
        project_id=project_id,
        workspace_id=workspace,
        visibility=scope,
    )
    assert not resource_visible_in_scope(
        resource_id=resource_id,
        project_id=project_id,
        workspace_id=workspace,
        project_is_personal=True,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=resource_id,
        project_id=project_id,
        workspace_id=workspace,
        project_is_personal=False,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=shared_id,
        project_id=project_id,
        workspace_id=workspace,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=resource_id,
        project_id=delegated_id,
        workspace_id=workspace,
        visibility=scope,
    )
    assert resource_visible_in_scope(
        resource_id=resource_id,
        project_id=None,
        workspace_id=workspace,
        visibility=scope,
    ) is (broad_scope != "unassigned")


@pytest.mark.parametrize("exclude_personal_projects", [False, True])
async def test_explicit_project_grant_survives_global_reserved_project_exclusion(
    async_session, exclude_personal_projects
):
    """Reserved-project exclusions restrict broad grants, not explicit delegation."""
    project_id, flow_id, owner_id = uuid4(), uuid4(), uuid4()
    async_session.add_all(
        [
            Folder(id=project_id, name="Reserved project", is_personal=False),
            Flow(id=flow_id, name="Reserved flow", folder_id=project_id, user_id=uuid4()),
        ]
    )
    await async_session.commit()
    for project_ids in ((), (project_id,)):
        scope = ResourceVisibilityScope(
            all_resources=True,
            excluded_global_project_ids=(project_id,),
            project_ids=project_ids,
            exclude_personal_projects=exclude_personal_projects,
        )
        stmt = restrict_to_owned_or_visible_scope(
            select(Flow.id),
            id_column=Flow.id,
            owner_clause=Flow.user_id == owner_id,
            project_column=Flow.folder_id,
            visibility=scope,
        )
        assert set((await async_session.exec(stmt)).all()) == ({flow_id} if project_ids else set())
        assert resource_visible_in_scope(
            resource_id=flow_id,
            project_id=project_id,
            project_is_personal=False,
            visibility=scope,
        ) is bool(project_ids)
