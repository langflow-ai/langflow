from fastapi import APIRouter, Depends, Request, HTTPException
from .local_runner import DefaultFlowRunner
from .protocol import FlowRunner
from typing import Annotated

router = APIRouter()

def get_runner() -> FlowRunner:
    return DefaultFlowRunner()

@router.post("/run")
async def run_endpoint(
    request: Request,
    runner: Annotated[FlowRunner, Depends(get_runner)],
):
    input_data = await request.json()
    try:
        return runner.run(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))