from http import HTTPStatus
from typing import Annotated

import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.message import Message
from dramatiq.results import ResultMissing, Results
from dramatiq.results.backends import RedisBackend
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger

from langflow.api.run_utils import simple_run_flow
from langflow.api.v1.schemas import SimplifiedAPIRequest, TaskStatusResponse
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.utils.async_helpers import run_until_complete

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)

result_backend = RedisBackend(url="redis://localhost:6379")
broker = RabbitmqBroker()
broker.add_middleware(Results(backend=result_backend))
dramatiq.set_broker(broker)


@dramatiq.actor(store_results=True)
def run_flow_task(
    flow: dict,
    input_request: dict,
    stream: bool = False,
    api_key_user: dict | None = None,
):
    try:
        flow_read = FlowRead(**flow)
        input_request_object = SimplifiedAPIRequest(**input_request)
        user_read = UserRead(**api_key_user)

        result = run_until_complete(
            simple_run_flow(
                flow=flow_read,
                input_request=input_request_object,
                stream=stream,
                api_key_user=user_read,
            )
        )
        return jsonable_encoder(result)
    except Exception as e:
        raise e


broker.declare_actor(run_flow_task)


@router.post("/task/start/{flow_id_or_name}")
async def run_flow_task_endpoint(
    flow: Annotated[FlowRead, Depends(get_flow_by_id_or_endpoint_name)],
    input_request: SimplifiedAPIRequest = SimplifiedAPIRequest(),
    stream: bool = False,
    api_key_user: UserRead = Depends(api_key_security),
):
    try:
        message = run_flow_task.send(
            flow=jsonable_encoder(flow),
            input_request=jsonable_encoder(input_request),
            stream=stream,
            api_key_user=jsonable_encoder(api_key_user),
        )
        return JSONResponse(status_code=HTTPStatus.ACCEPTED, content={"task_id": message.message_id})
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    try:
        message = Message(
            message_id=task_id, actor_name="run_flow_task", queue_name="default", args=[], kwargs={}, options={}
        )
        result = result_backend.get_result(message)
        return TaskStatusResponse(status="COMPLETED", result=result)
    except ResultMissing as e:
        return TaskStatusResponse(status=e, result=None)
