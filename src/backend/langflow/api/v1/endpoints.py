from langflow.database.models.flow import Flow
from langflow.processing.process import process_graph_cached, process_tweaks
from langflow.utils.logger import logger
from importlib.metadata import version

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer

from langflow.api.v1.schemas import (
    PredictRequest,
    PredictResponse,
)

from langflow.interface.types import build_langchain_types_dict
from langflow.database.base import get_session
from sqlmodel import Session

# build router
router = APIRouter(tags=["Base"])

security = HTTPBearer()


def get_flow_from_token(
    bearer: HTTPBearer = Depends(security), session: Session = Depends(get_session)
) -> str:
    # Extract the token, which is the flow_id in this case
    flow_id = bearer.credentials
    # Check if the flow_id exists in the database
    flow = session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return flow


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


@router.post("/predict/{flow_id}", response_model=PredictResponse)
async def predict_flow(
    predict_request: PredictRequest,
    flow_id: str,
    session: Session = Depends(get_session),
):
    """
    Endpoint to process a message using the flow passed in the bearer token.
    """

    try:
        flow = session.get(Flow, flow_id)
        if flow is None:
            raise ValueError(f"Flow {flow_id} not found")
        graph_data = flow.data
        if predict_request.tweaks:
            graph_data = process_tweaks(graph_data, predict_request.tweaks)

        response = process_graph_cached(graph_data, predict_request.message)
        return PredictResponse(
            result=response.get("result", ""),
            intermediate_steps=response.get("thought", ""),
        )
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# get endpoint to return version of langflow
@router.get("/version")
def get_version():
    return {"version": version("langflow")}
