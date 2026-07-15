"""Structured visibility coverage for resources without domain columns."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.api.v1 import knowledge_bases as knowledge_bases_api
from langflow.api.v1 import memories as memories_api
from langflow.api.v1 import variable as variable_api
from langflow.api.v2 import files as files_api
from langflow.services.authorization.listing import restrict_to_owned_or_visible_scope
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_settings_service
from langflow.services.variable.service import DatabaseVariableService
from lfx.services.authorization.base import ResourceVisibilityScope
from sqlmodel import select


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    async def exec(self, statement):
        self.statement = statement
        return []


@pytest.mark.anyio
async def test_file_list_uses_global_structured_visibility(monkeypatch):
    actor = SimpleNamespace(id=uuid4())
    session = _CapturingSession()
    visibility = ResourceVisibilityScope(all_resources=True)

    monkeypatch.setattr(files_api, "ensure_file_permission", AsyncMock())
    monkeypatch.setattr(files_api, "get_mcp_file", AsyncMock(return_value="_mcp_servers"))
    monkeypatch.setattr(files_api, "visible_scope_prefilter", AsyncMock(return_value=visibility), raising=False)
    monkeypatch.setattr(files_api, "visible_id_prefilter", AsyncMock(return_value=None))

    await files_api.list_files(current_user=actor, session=session)

    assert session.statement is not None
    assert UserFile.user_id.key not in str(session.statement.whereclause)


@pytest.mark.anyio
async def test_knowledge_base_list_forwards_concrete_structured_visibility(monkeypatch, tmp_path):
    actor = SimpleNamespace(id=uuid4(), username="actor")
    visibility = ResourceVisibilityScope(resource_ids=(uuid4(),))
    list_owned_or_visible = AsyncMock(return_value=[])
    list_by_user = AsyncMock(return_value=[])

    monkeypatch.setattr(knowledge_bases_api, "_guard_kb_action", AsyncMock())
    monkeypatch.setattr(knowledge_bases_api.KBStorageHelper, "get_root_path", lambda: tmp_path)
    monkeypatch.setattr(
        knowledge_bases_api,
        "visible_scope_prefilter",
        AsyncMock(return_value=visibility),
        raising=False,
    )
    monkeypatch.setattr(knowledge_bases_api, "visible_id_prefilter", AsyncMock(return_value=None))
    monkeypatch.setattr(knowledge_bases_api.knowledge_base_service, "list_by_user", list_by_user)
    monkeypatch.setattr(
        knowledge_bases_api.knowledge_base_service,
        "list_owned_or_visible",
        list_owned_or_visible,
    )

    result = await knowledge_bases_api.list_knowledge_bases(
        current_user=actor,
        job_service=MagicMock(),
    )

    assert result == []
    list_owned_or_visible.assert_awaited_once_with(actor.id, visibility)
    list_by_user.assert_not_awaited()


@pytest.mark.anyio
async def test_memory_base_list_forwards_structured_visibility(monkeypatch):
    actor = SimpleNamespace(id=uuid4())
    visibility = ResourceVisibilityScope(project_ids=(uuid4(),))
    service = MagicMock()
    service.list_for_user_stmt.return_value = select(Variable)
    page = MagicMock()

    @asynccontextmanager
    async def fake_session_scope():
        yield MagicMock()

    monkeypatch.setattr(memories_api, "session_scope", fake_session_scope)
    monkeypatch.setattr(memories_api, "get_memory_base_service", lambda: service)
    monkeypatch.setattr(memories_api, "apaginate", AsyncMock(return_value=page))
    monkeypatch.setattr(memories_api, "visible_scope_prefilter", AsyncMock(return_value=visibility), raising=False)
    monkeypatch.setattr(memories_api, "visible_id_prefilter", AsyncMock(return_value=None))

    result = await memories_api.list_memory_bases(
        current_user=actor,
        params=MagicMock(),
    )

    assert result is page
    service.list_for_user_stmt.assert_called_once_with(
        user_id=actor.id,
        flow_id=None,
        visibility=visibility,
    )


@pytest.mark.anyio
async def test_variable_list_forwards_global_structured_visibility(monkeypatch):
    actor = SimpleNamespace(id=uuid4())
    visibility = ResourceVisibilityScope(all_resources=True)
    service = DatabaseVariableService(get_settings_service())
    get_all = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "get_all", get_all)

    monkeypatch.setattr(variable_api, "ensure_variable_permission", AsyncMock())
    monkeypatch.setattr(variable_api, "get_variable_service", lambda: service)
    monkeypatch.setattr(variable_api, "visible_scope_prefilter", AsyncMock(return_value=visibility), raising=False)
    monkeypatch.setattr(variable_api, "visible_id_prefilter", AsyncMock(return_value=None))

    result = await variable_api.read_variables(
        session=MagicMock(),
        current_user=actor,
    )

    assert result == []
    get_all.assert_awaited_once_with(
        user_id=actor.id,
        session=ANY,
        visibility=visibility,
    )


def test_unscoped_visibility_uses_global_and_concrete_grants_but_not_domain_grants():
    actor_id = uuid4()
    shared_id = uuid4()

    global_statement = restrict_to_owned_or_visible_scope(
        select(Variable),
        id_column=Variable.id,
        owner_clause=Variable.user_id == actor_id,
        visibility=ResourceVisibilityScope(all_resources=True),
    )
    concrete_statement = restrict_to_owned_or_visible_scope(
        select(Variable),
        id_column=Variable.id,
        owner_clause=Variable.user_id == actor_id,
        visibility=ResourceVisibilityScope(resource_ids=(shared_id,)),
    )
    domain_only_statement = restrict_to_owned_or_visible_scope(
        select(Variable),
        id_column=Variable.id,
        owner_clause=Variable.user_id == actor_id,
        visibility=ResourceVisibilityScope(workspace_ids=(uuid4(),), project_ids=(uuid4(),)),
    )

    assert not global_statement._where_criteria
    assert "variable.id IN" in str(concrete_statement.whereclause)
    assert "variable.user_id =" in str(concrete_statement.whereclause)
    assert "variable.id IN" not in str(domain_only_statement.whereclause)
    assert "variable.user_id =" in str(domain_only_statement.whereclause)
