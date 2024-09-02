from temporalio import activity

from langflow.api.run_utils import simple_run_flow
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead


@activity.defn
async def run_flow_activity(
    flow: FlowRead,
    input_request: SimplifiedAPIRequest,
    stream: bool = False,
    api_key_user: UserRead | None = None,
) -> dict:
    result = await simple_run_flow(
        flow=flow,
        input_request=input_request,
        stream=stream,
        api_key_user=api_key_user,
    )
    return result
