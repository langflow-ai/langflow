from typing import List

from fastapi import APIRouter, Depends, HTTPException
from langflow.services.deps import get_monitor_service
from langflow.services.monitor.schema import MessageModel, TransactionModel
from langflow.services.monitor.service import MonitorService
from loguru import logger

# build router
router = APIRouter(prefix="/monitor", tags=["Monitor"])


@router.get("/transactions", status_code=200, response_model=List[TransactionModel])
def get_transactions(monitor_service: MonitorService = Depends(get_monitor_service)):
    try:
        df = monitor_service.to_df("transactions")
        # TODO: Add filters
        return df.to_dict(orient="records")
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages", status_code=200, response_model=List[MessageModel])
def get_messages(monitor_service: "MonitorService" = Depends(get_monitor_service)):
    try:
        df = monitor_service.to_df("messages")
        # TODO: Add filters
        return df.to_dict(orient="records")
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
