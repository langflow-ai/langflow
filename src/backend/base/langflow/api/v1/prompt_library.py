"""Prompt Library API proxy endpoints."""

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from loguru import logger

from langflow.services.deps import get_prompt_service

router = APIRouter(prefix="/prompt-library", tags=["Prompt Library"])


def _extract_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    return None


@router.get("/prompts/versions")
async def get_prompts_with_versions(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: str | None = Query(None),
    name: str | None = Query(None),
) -> dict[str, Any]:
    """Get prompts with version status."""
    ps = get_prompt_service()
    if not ps.ready:
        raise HTTPException(status_code=503, detail="Prompt service not available")

    token = _extract_token(request)
    result = await ps.get_prompts_with_versions(token=token)
    return result


@router.get("/prompts/{prompt_id}/versions")
async def get_prompt_versions(
    request: Request,
    prompt_id: str = Path(..., description="Prompt ID"),
) -> dict[str, Any]:
    """Get all versions for a specific prompt."""
    ps = get_prompt_service()
    if not ps.ready:
        raise HTTPException(status_code=503, detail="Prompt service not available")

    token = _extract_token(request)
    result = await ps.get_prompt_versions(prompt_id, token=token)
    return result


@router.post("/prompts/")
async def create_prompt(
    request: Request,
    prompt_data: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Create a new prompt in the Prompt Library."""
    ps = get_prompt_service()
    if not ps.ready:
        raise HTTPException(status_code=503, detail="Prompt service not available")

    token = _extract_token(request)
    result = await ps.create_prompt(prompt_data, token=token)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/prompts/{prompt_id}/versions")
async def create_version(
    request: Request,
    prompt_id: str = Path(..., description="Prompt ID"),
    version_data: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Create a new version for a prompt."""
    ps = get_prompt_service()
    if not ps.ready:
        raise HTTPException(status_code=503, detail="Prompt service not available")

    token = _extract_token(request)
    result = await ps.create_version(prompt_id, version_data, token=token)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.put("/prompts/{prompt_id}/versions/{version}")
async def update_version(
    request: Request,
    prompt_id: str = Path(..., description="Prompt ID"),
    version: int = Path(..., ge=1, description="Version number"),
    version_data: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Update an existing version (only for DRAFT versions)."""
    ps = get_prompt_service()
    if not ps.ready:
        raise HTTPException(status_code=503, detail="Prompt service not available")

    token = _extract_token(request)
    result = await ps.update_version(prompt_id, version, version_data, token=token)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/prompts/{prompt_id}/versions/{version}/submit")
async def submit_for_review(
    request: Request,
    prompt_id: str = Path(..., description="Prompt ID"),
    version: int = Path(..., ge=1, description="Version number"),
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Submit/promote a version to the next stage."""
    ps = get_prompt_service()
    if not ps.ready:
        raise HTTPException(status_code=503, detail="Prompt service not available")

    token = _extract_token(request)
    comment = payload.get("comment", "")
    result = await ps.submit_for_review(prompt_id, version, token=token, comment=comment)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result
