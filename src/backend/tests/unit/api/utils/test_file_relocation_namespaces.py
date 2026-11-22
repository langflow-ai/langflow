"""Namespace selection for file relocation."""

from uuid import uuid4

import pytest
from langflow.api.utils.file_relocation import _namespaces
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize("collides_with_user", [False, True])
async def test_flow_namespaces_skip_only_colliding_raw_flow_ids(active_user, collides_with_user):
    flow_id = active_user.id if collides_with_user else uuid4()
    async with session_scope() as session:
        session.add(Flow(id=flow_id, user_id=active_user.id, name="Relocation collision", data={}))
        await session.commit()

    namespaces = await _namespaces(None)

    assert f"flow-{flow_id}" in namespaces
    if collides_with_user:
        assert namespaces.count(str(flow_id)) == 1
    else:
        assert str(flow_id) in namespaces
