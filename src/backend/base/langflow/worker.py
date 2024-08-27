from typing import TYPE_CHECKING

from asyncer import syncify

from langflow.api.run_utils import simple_run_flow
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.core.celery_app import celery_app
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead

if TYPE_CHECKING:
    pass


@celery_app.task(acks_late=True)
def test_celery(word: str) -> str:
    return f"test task return {word}"


@celery_app.task(bind=True, max_retries=3)
def run_flow_task(
    self,
    flow: dict,
    input_request: dict,
    stream: bool = False,
    api_key_user: dict | None = None,
):
    try:
        flow_read = FlowRead(**flow)
        input_request_object = SimplifiedAPIRequest(**input_request)
        user_read = UserRead(**api_key_user)
        result = syncify(simple_run_flow)(
            flow=flow_read,
            input_request=input_request_object,
            stream=stream,
            api_key_user=user_read,
        )
        return result
    except Exception as e:
        raise self.retry(exc=e)
