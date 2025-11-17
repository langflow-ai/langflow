from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from langflow.logging.logger import logger

router = APIRouter(prefix="/observability", tags=["Observability"])


def _get_base_url() -> str:
    """Get the external monitoring/observability base URL from environment.

    Returns:
        str: Base URL ending with '/observability'.

    Raises:
        HTTPException: If the environment variable is missing.
    """
    base = os.getenv("MONITORING_AND_OBSERVABILITY_SERVICE_URL")
    if not base or not base.strip():
        raise HTTPException(status_code=500, detail="MONITORING_AND_OBSERVABILITY_SERVICE_URL is not set")
    base = base.rstrip("/")
    return f"{base}/observability"


async def _proxy_get(path: str, params: dict[str, Any]) -> Any:
    """Proxy a GET request to the external observability service.

    Args:
        path: Path appended to the base '/observability' URL.
        params: Query parameters to forward.

    Returns:
        The JSON response from the external service.
    """
    base_url = _get_base_url()
    url = f"{base_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        # Bubble up the original status code and detail if available
        detail = None
        try:
            detail = e.response.json()
        except Exception:  # noqa: BLE001
            detail = e.response.text
        await logger.aerror(f"Observability proxy GET failed: {e.response.status_code} {detail}")
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except Exception as e:  # noqa: BLE001
        await logger.aexception(f"Observability proxy GET error: {e!s}")
        raise HTTPException(status_code=500, detail="Observability service request failed")


# Traces
@router.get("/agents/{agent_name}/traces")
async def get_agent_specific_traces(
    agent_name: str,
    days: int = Query(..., ge=0),
    include_observations: bool = Query(False),
    limit: int = Query(50, ge=0),
    offset: int = Query(0, ge=0),
):
    return await _proxy_get(
        f"/agents/{agent_name}/traces",
        {"days": days, "include_observations": include_observations, "limit": limit, "offset": offset},
    )


@router.get("/models/{model_name}/traces")
async def get_model_specific_traces(
    model_name: str,
    days: int = Query(..., ge=0),
    include_observations: bool = Query(False),
    limit: int = Query(50, ge=0),
    offset: int = Query(0, ge=0),
):
    return await _proxy_get(
        f"/models/{model_name}/traces",
        {"days": days, "include_observations": include_observations, "limit": limit, "offset": offset},
    )


@router.get("/traces")
async def get_traces(
    days: int | None = Query(None, ge=0),
    include_observations: bool | None = Query(None),
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    sort_by: str | None = Query(None),
    order: str | None = Query(None),
    agent_name: str | None = Query(None),
    model_name: str | None = Query(None),
):
    params: dict[str, Any] = {
        k: v
        for k, v in {
            "days": days,
            "include_observations": include_observations,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "order": order,
            "agent_name": agent_name,
            "model_name": model_name,
        }.items()
        if v is not None
    }
    return await _proxy_get("/traces", params)


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, include_observations: bool = Query(False)):
    return await _proxy_get(f"/traces/{trace_id}", {"include_observations": include_observations})


# Dashboard: Performance
@router.get("/dashboard/agents/performance")
async def get_agents_performance(days: int = Query(..., ge=0), limit: int = Query(10, ge=0)):
    return await _proxy_get("/dashboard/agents/performance", {"days": days, "limit": limit})


@router.get("/dashboard/models/performance")
async def get_models_performance(days: int = Query(..., ge=0), limit: int = Query(10, ge=0)):
    return await _proxy_get("/dashboard/models/performance", {"days": days, "limit": limit})


@router.get("/dashboard/projects/performance")
async def get_projects_performance(days: int = Query(..., ge=0), limit: int = Query(10, ge=0)):
    return await _proxy_get("/dashboard/projects/performance", {"days": days, "limit": limit})


# Dashboard: Latency Trends
@router.get("/dashboard/models/latency-trends")
async def get_models_latency_trends(days: int = Query(..., ge=0), top_models: int = Query(5, ge=0)):
    return await _proxy_get("/dashboard/models/latency-trends", {"days": days, "top_models": top_models})


@router.get("/dashboard/agents/latency-trends")
async def get_agents_latency_trends(days: int = Query(..., ge=0), top_agents: int = Query(5, ge=0)):
    return await _proxy_get("/dashboard/agents/latency-trends", {"days": days, "top_agents": top_agents})


@router.get("/dashboard/projects/latency-trends")
async def get_projects_latency_trends(days: int = Query(..., ge=0), top_agents: int = Query(5, ge=0)):
    return await _proxy_get("/dashboard/projects/latency-trends", {"days": days, "top_agents": top_agents})


# Dashboard: Summary
@router.get("/dashboard/summary")
async def get_dashboard_summary(timeframe: str = Query("24h")):
    return await _proxy_get("/dashboard/summary", {"timeframe": timeframe})


# Dashboard: Cost Breakdown
@router.get("/dashboard/models/cost-breakdown")
async def get_models_cost_breakdown(days: int = Query(..., ge=0)):
    return await _proxy_get("/dashboard/models/cost-breakdown", {"days": days})


@router.get("/dashboard/projects/cost-breakdown")
async def get_projects_cost_breakdown(days: int = Query(..., ge=0)):
    return await _proxy_get("/dashboard/projects/cost-breakdown", {"days": days})


@router.get("/dashboard/agents/cost-breakdown")
async def get_agents_cost_breakdown(days: int = Query(..., ge=0)):
    return await _proxy_get("/dashboard/agents/cost-breakdown", {"days": days})


# Dashboard: Usage Trends
@router.get("/dashboard/usage-trends")
async def get_usage_trends(days: int = Query(..., ge=0), entity_type: str = Query(...), entity_name: str = Query(...)):
    return await _proxy_get(
        "/dashboard/usage-trends",
        {"days": days, "entity_type": entity_type, "entity_name": entity_name},
    )


@router.get("/dashboard/projects/usage-trends")
async def get_projects_usage_trends(days: int = Query(..., ge=0), entity_name: str = Query(...)):
    return await _proxy_get("/dashboard/projects/usage-trends", {"days": days, "entity_name": entity_name})


# Dashboard: Traces
@router.get("/dashboard/traces")
async def get_dashboard_traces(
    days: int | None = Query(None, ge=0),
    include_observations: bool | None = Query(None),
    top_agents: int | None = Query(None, ge=0),
    top_models: int | None = Query(None, ge=0),
):
    params: dict[str, Any] = {
        k: v
        for k, v in {
            "days": days,
            "include_observations": include_observations,
            "top_agents": top_agents,
            "top_models": top_models,
        }.items()
        if v is not None
    }
    return await _proxy_get("/dashboard/traces", params)