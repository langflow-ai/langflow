from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from .local_runner import DefaultFlowRunner
from .protocol import FlowExecutionRequest, FlowRunner

router = APIRouter()


def get_runner() -> FlowRunner:
    return DefaultFlowRunner()


@router.post("/run")
async def run_endpoint(
    background_tasks: BackgroundTasks,
    input_request: FlowExecutionRequest,
    stream: bool = False,
    runner=Annotated[FlowRunner, Depends(get_runner)],
):
    try:
        return await runner.run(
            background_tasks=background_tasks,
            input_request=input_request,
            stream=stream,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
