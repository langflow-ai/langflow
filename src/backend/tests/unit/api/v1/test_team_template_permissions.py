from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.team_templates import _ensure_template_delete
from langflow.services.database.models.team_template import TeamTemplate


def _template(owner_id):
    return TeamTemplate(
        name="Template",
        category="assistants",
        flow_data={"nodes": [], "edges": []},
        created_by=owner_id,
    )


def test_langflow_user_can_delete_another_users_template() -> None:
    row = _template(uuid4())
    user = SimpleNamespace(id=uuid4(), username="langflow", is_superuser=False)

    _ensure_template_delete(row, user)


def test_regular_user_cannot_delete_another_users_template() -> None:
    row = _template(uuid4())
    user = SimpleNamespace(id=uuid4(), username="regular-user", is_superuser=False)

    with pytest.raises(HTTPException) as exc_info:
        _ensure_template_delete(row, user)

    assert exc_info.value.status_code == 403
