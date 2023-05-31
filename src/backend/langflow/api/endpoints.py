from langflow.utils.logger import logger
from importlib.metadata import version

from fastapi import APIRouter, File, HTTPException, UploadFile

from langflow.api.schemas import (
    ExportedFlow,
    GraphData,
    PredictRequest,
    PredictResponse,
)
from langflow.interface.run import process_graph_cached
from langflow.interface.types import build_langchain_types_dict
from langflow.cache import cache_manager

# build router
router = APIRouter(tags=["Base"])


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


@router.post("/predict", response_model=PredictResponse)
async def get_load(predict_request: PredictRequest):
    try:
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


@router.get("/health")
def get_health():
    return {"status": "OK"}


# Make an endpoint to upload  a file using the client_id and
# cache the file in the backend
@router.post("/uploadfile/{client_id}")
async def create_upload_file(client_id: str, file: UploadFile = File(...)):

    # TODO: Implement this endpoint
