import logging
from importlib.metadata import version

from fastapi import APIRouter, HTTPException

from langflow.api.v1.schemas import (
    ExportedFlow,
    GraphData,
    PredictRequest,
    PredictResponse,
)

from langflow.interface.types import build_langchain_types_dict

# build router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


@router.post("/predict", response_model=PredictResponse)
async def get_load(predict_request: PredictRequest):
    try:
        from langflow.processing.process import process_graph_cached

        exported_flow: ExportedFlow = predict_request.exported_flow
        graph_data: GraphData = exported_flow.data
        data = graph_data.dict()
        response = process_graph_cached(data, predict_request.message)
        return PredictResponse(result=response.get("result", ""))
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# get endpoint to return version of langflow
@router.get("/version")
def get_version():
    return {"version": version("langflow")}
