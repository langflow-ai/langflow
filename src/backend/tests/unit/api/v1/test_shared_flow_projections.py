from uuid import uuid4

import pytest
from langflow.api.v1.flow_conflict_routes import fork_flow
from langflow.api.v1.flow_fork import FlowFork
from langflow.api.v1.schemas.replacement_operations import ProjectReplacementResult
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.folder.model import FolderRead
from langflow.services.deps import get_storage_service, session_scope


def _graph(value):
    template = {
        "credential": {"name": "credential", "password": True, "value": value},
        "label": {"name": "label", "value": "keep"},
    }
    return {"nodes": [{"id": "example", "data": {"node": {"template": template}}}], "edges": []}


@pytest.mark.parametrize(
    ("is_owner", "override", "expected"),
    [(False, None, None), (True, None, "source"), (False, "edited", "edited")],
)
async def test_fork_uses_callers_graph(active_user, is_owner, override, expected):
    source = Flow(name="Source", data=_graph("source"), user_id=active_user.id if is_owner else uuid4())
    fork = FlowFork(data=_graph(override)) if override else FlowFork()

    async with session_scope() as session:
        result = await fork_flow(
            session=session,
            flow_id=source.id,
            flow=source,
            fork=fork,
            current_user=active_user,
            storage_service=get_storage_service(),
        )
        assert result.data == _graph(expected)
        assert result.user_id == active_user.id
        assert source.data == _graph("source")


def test_replacement_result_redacts_new_and_historical_receipts():
    flow = FlowRead(id=uuid4(), name="Source", data=_graph("source"), user_id=uuid4(), folder_id=None)
    project = FolderRead(id=uuid4(), name="Example", parent_id=None)
    result = ProjectReplacementResult(project=project, flows=[flow])
    receipt = result.model_dump(mode="json")

    assert receipt["flows"][0]["data"] == _graph(None)
    assert flow.data == _graph("source")

    receipt["flows"][0]["data"] = _graph("historical")
    replayed = ProjectReplacementResult.model_validate(receipt)
    assert replayed.flows[0].data == _graph(None)
    assert receipt["flows"][0]["data"] == _graph("historical")
