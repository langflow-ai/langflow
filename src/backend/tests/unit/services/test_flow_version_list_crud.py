from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import (
    get_flow_version_entry,
    get_flow_version_list_simple,
    get_flow_versions_with_provider_status,
)
from langflow.services.database.models.flow_version.model import FlowVersion, FlowVersionRead
from langflow.services.database.models.user.model import User
from sqlalchemy import event, inspect
from sqlalchemy.exc import InvalidRequestError


@pytest.mark.parametrize("with_provider", [False, True])
@pytest.mark.parametrize("data", [None, {"nodes": [{"id": "saved-node"}], "edges": []}])
async def test_list_versions_loads_only_metadata(async_session, with_provider, data):
    user = User(username=f"version-author-{uuid4()}", password="unused")  # noqa: S106
    async_session.add(user)
    await async_session.flush()
    flow = Flow(name="version-list", user_id=user.id, data=data)
    async_session.add(flow)
    await async_session.flush()
    versions = [
        FlowVersion(
            flow_id=flow.id,
            user_id=user.id,
            version_number=number,
            data=data,
            description=f"Snapshot {number}",
            retained=number == 2,
            retained_reason="keep" if number == 2 else None,
        )
        for number in range(1, 4)
    ]
    async_session.add_all(versions)
    await async_session.flush()
    flow_id, user_id, version_id = flow.id, user.id, versions[1].id
    expected = FlowVersionRead.model_validate(versions[1], from_attributes=True).model_dump(mode="json")
    # A fresh identity map ensures the query cannot reuse a previously loaded payload.
    async_session.expunge_all()

    selected_columns = []

    def capture_columns(_conn, cursor, _statement, _parameters, _context, _executemany):
        selected_columns.append([column[0] for column in cursor.description])

    engine = async_session.bind.sync_engine
    event.listen(engine, "after_cursor_execute", capture_columns)
    try:
        if with_provider:
            rows = await get_flow_versions_with_provider_status(
                async_session, flow_id, user_id, provider_account_id=uuid4(), limit=1, offset=1
            )
        else:
            rows = await get_flow_version_list_simple(async_session, flow_id, user_id, limit=1, offset=1)

        assert len(rows) == 1
        version, is_deployed = rows[0]
        assert version.id == version_id
        assert is_deployed is False
        assert "data" in inspect(version).unloaded
        assert FlowVersionRead.model_validate(version, from_attributes=True).model_dump(mode="json") == expected
        with pytest.raises(InvalidRequestError, match="raiseload"):
            _ = version.data
        assert len(selected_columns) == 1
        assert "data" not in selected_columns[0]
    finally:
        event.remove(engine, "after_cursor_execute", capture_columns)

    # An explicit detail read must still load the payload, even in the same session.
    detail = await get_flow_version_entry(async_session, version_id, user_id)
    assert detail is not None
    assert "data" not in inspect(detail).unloaded
    assert detail.data == data
