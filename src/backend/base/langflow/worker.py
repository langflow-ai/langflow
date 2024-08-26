from typing import TYPE_CHECKING, Optional

from asyncer import syncify

from langflow.api.run_utils import simple_run_flow
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.core.celery_app import celery_app
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    pass


@celery_app.task(acks_late=True)
def test_celery(word: str) -> str:
    return f"test task return {word}"


@celery_app.task(bind=True, max_retries=3)
def run_flow_task(
    self,
    flow: FlowRead,
    input_request: SimplifiedAPIRequest,
    stream: bool = False,
    api_key_user: Optional[User] = None,
):
    try:
        result = syncify(simple_run_flow)(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
        )
        return result
    except Exception as e:
        raise self.retry(exc=e)
