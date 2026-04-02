"""CRUD API for custom OpenAI-compatible providers."""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.custom_provider.model import (
    CustomProvider,
    CustomProviderCreate,
    CustomProviderModel,
    CustomProviderModelRead,
    CustomProviderModelSchema,
    CustomProviderRead,
    CustomProviderUpdate,
)

router = APIRouter(prefix="/custom-providers", tags=["Custom Providers"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RFC-1918 / loopback / link-local networks to block (SSRF prevention)
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_MAX_DISCOVERED_MODELS = 500


# ---------------------------------------------------------------------------
# SSRF validation
# ---------------------------------------------------------------------------


def _validate_url_no_ssrf(url: str) -> None:
    """Raise HTTPException(400) if *url* targets an internal/loopback address.

    Checks:
    1. Scheme must be http or https.
    2. DNS resolution must not return an RFC-1918 / loopback / link-local address.

    Set LANGFLOW_ALLOW_PRIVATE_URLS=true to skip the private-address check
    (useful for development or self-hosted environments with internal gateways).
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="base_url must use http or https scheme")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="base_url is missing a hostname")

    # Allow private/internal URLs when explicitly opted in
    if os.environ.get("LANGFLOW_ALLOW_PRIVATE_URLS", "").lower() in ("true", "1", "yes"):
        return

    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}") from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        raw_ip = sockaddr[0]
        try:
            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise HTTPException(
                    status_code=400,
                    detail=f"base_url resolves to a private/loopback address ({raw_ip}), which is not allowed",
                )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build_read(cp: CustomProvider) -> CustomProviderRead:
    """Build a CustomProviderRead from a CustomProvider, loading models."""
    return CustomProviderRead(
        id=cp.id,
        user_id=cp.user_id,
        name=cp.name,
        base_url=cp.base_url,
        models=[
            CustomProviderModelRead(
                id=m.id,
                provider_id=m.provider_id,
                name=m.name,
                tool_calling=m.tool_calling,
            )
            for m in cp.models
        ],
        created_at=cp.created_at,
        updated_at=cp.updated_at,
    )


def _add_models(session, provider_id: UUID, model_schemas: list[CustomProviderModelSchema]) -> None:
    """Persist a list of model schemas for the given provider."""
    for schema in model_schemas:
        db_model = CustomProviderModel(
            provider_id=provider_id,
            name=schema.name,
            tool_calling=schema.tool_calling,
        )
        session.add(db_model)


# ---------------------------------------------------------------------------
# Response schema for discover-models
# ---------------------------------------------------------------------------


class DiscoverModelsResponse(BaseModel):
    models: list[str]
    discovery_supported: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=CustomProviderRead, status_code=201)
async def create_custom_provider(
    *,
    session: DbSession,
    body: CustomProviderCreate,
    current_user: CurrentActiveUser,
) -> CustomProviderRead:
    """Create a new custom provider with optional models."""
    # Normalize base_url
    body.base_url = body.base_url.rstrip("/")

    # SSRF check
    _validate_url_no_ssrf(body.base_url)

    # Duplicate name check (scoped to user)
    existing = (
        await session.exec(
            select(CustomProvider).options(selectinload(CustomProvider.models)).where(
                CustomProvider.user_id == current_user.id,
                CustomProvider.name == body.name,
            )
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A provider with this name already exists")

    encrypted_key = auth_utils.encrypt_api_key(body.api_key)

    cp = CustomProvider(
        user_id=current_user.id,
        name=body.name,
        base_url=body.base_url,
        api_key=encrypted_key,
    )
    session.add(cp)
    await session.flush()  # populate cp.id

    if body.models:
        _add_models(session, cp.id, body.models)
        await session.flush()

    # Re-query with eager load to include models in response
    # (DbSession auto-commits at end of request)
    cp = (
        await session.exec(
            select(CustomProvider).options(selectinload(CustomProvider.models)).where(
                CustomProvider.id == cp.id,
            )
        )
    ).one()
    return _build_read(cp)


@router.get("/", response_model=list[CustomProviderRead])
async def list_custom_providers(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> list[CustomProviderRead]:
    """List all custom providers for the current user."""
    results = (
        await session.exec(
            select(CustomProvider)
            .options(selectinload(CustomProvider.models))
            .where(CustomProvider.user_id == current_user.id)
            .order_by(CustomProvider.created_at)
        )
    ).all()
    return [_build_read(cp) for cp in results]


@router.get("/{provider_id}", response_model=CustomProviderRead)
async def get_custom_provider(
    *,
    session: DbSession,
    provider_id: UUID,
    current_user: CurrentActiveUser,
) -> CustomProviderRead:
    """Get a single custom provider."""
    cp = (
        await session.exec(
            select(CustomProvider).options(selectinload(CustomProvider.models)).where(
                CustomProvider.id == provider_id,
                CustomProvider.user_id == current_user.id,
            )
        )
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Custom provider not found")
    return _build_read(cp)


@router.patch("/{provider_id}", response_model=CustomProviderRead)
async def update_custom_provider(
    *,
    session: DbSession,
    provider_id: UUID,
    body: CustomProviderUpdate,
    current_user: CurrentActiveUser,
) -> CustomProviderRead:
    """Update a custom provider.  All fields are optional.

    If *models* is provided the existing model list is replaced entirely.
    If *api_key* is provided it is re-encrypted.
    If *base_url* is provided SSRF validation is re-run.
    """
    # Do NOT eager-load models here — if models are being replaced,
    # loaded ORM objects would conflict with the delete operation.
    cp = (
        await session.exec(
            select(CustomProvider).where(
                CustomProvider.id == provider_id,
                CustomProvider.user_id == current_user.id,
            )
        )
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Custom provider not found")

    if body.name is not None:
        collision = (
            await session.exec(
                select(CustomProvider).where(
                    CustomProvider.user_id == current_user.id,
                    CustomProvider.name == body.name,
                    CustomProvider.id != provider_id,
                )
            )
        ).first()
        if collision:
            raise HTTPException(status_code=400, detail="A provider with this name already exists")
        cp.name = body.name

    if body.base_url is not None:
        new_url = body.base_url.rstrip("/")
        _validate_url_no_ssrf(new_url)
        cp.base_url = new_url

    if body.api_key is not None:
        cp.api_key = auth_utils.encrypt_api_key(body.api_key)

    new_model_objects: list[CustomProviderModel] | None = None
    if body.models is not None:
        # Delete existing models via bulk SQL (avoids ORM identity map conflicts)
        from sqlalchemy import delete as sa_delete

        await session.exec(sa_delete(CustomProviderModel).where(CustomProviderModel.provider_id == provider_id))  # type: ignore[arg-type]
        await session.flush()

        new_model_objects = []
        for schema in body.models:
            m = CustomProviderModel(provider_id=cp.id, name=schema.name, tool_calling=schema.tool_calling)
            session.add(m)
            new_model_objects.append(m)
        await session.flush()

    session.add(cp)
    await session.flush()

    # Build response directly from objects we just wrote
    if new_model_objects is not None:
        model_reads = [
            CustomProviderModelRead(id=m.id, provider_id=m.provider_id, name=m.name, tool_calling=m.tool_calling)
            for m in new_model_objects
        ]
    else:
        # No model changes — query current models
        models = (
            await session.exec(
                select(CustomProviderModel).where(CustomProviderModel.provider_id == cp.id)
            )
        ).all()
        model_reads = [
            CustomProviderModelRead(id=m.id, provider_id=m.provider_id, name=m.name, tool_calling=m.tool_calling)
            for m in models
        ]

    return CustomProviderRead(
        id=cp.id, user_id=cp.user_id, name=cp.name, base_url=cp.base_url,
        models=model_reads, created_at=cp.created_at, updated_at=cp.updated_at,
    )


@router.delete("/{provider_id}", status_code=204)
async def delete_custom_provider(
    *,
    session: DbSession,
    provider_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a custom provider (and its models via cascade)."""
    cp = (
        await session.exec(
            select(CustomProvider).options(selectinload(CustomProvider.models)).where(
                CustomProvider.id == provider_id,
                CustomProvider.user_id == current_user.id,
            )
        )
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Custom provider not found")

    await session.delete(cp)


@router.post("/{provider_id}/validate", response_model=dict)
async def validate_custom_provider(
    *,
    session: DbSession,
    provider_id: UUID,
    current_user: CurrentActiveUser,
) -> dict:
    """Probe the provider's /models endpoint to verify connectivity and credentials."""
    cp = (
        await session.exec(
            select(CustomProvider).options(selectinload(CustomProvider.models)).where(
                CustomProvider.id == provider_id,
                CustomProvider.user_id == current_user.id,
            )
        )
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Custom provider not found")

    _validate_url_no_ssrf(cp.base_url)

    api_key = auth_utils.decrypt_api_key(cp.api_key)
    url = f"{cp.base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if response.status_code < 400:
            return {"valid": True, "error": None}
        return {"valid": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Request timed out"}
    except httpx.RequestError as exc:
        return {"valid": False, "error": str(exc)}


@router.get("/{provider_id}/discover-models", response_model=DiscoverModelsResponse)
async def discover_models(
    *,
    session: DbSession,
    provider_id: UUID,
    current_user: CurrentActiveUser,
) -> DiscoverModelsResponse:
    """Discover models by calling GET {base_url}/models (OpenAI list format).

    Returns an empty list (not an error) when the endpoint responds with 404 or 405.
    Caps the result at 500 model IDs.
    """
    cp = (
        await session.exec(
            select(CustomProvider).options(selectinload(CustomProvider.models)).where(
                CustomProvider.id == provider_id,
                CustomProvider.user_id == current_user.id,
            )
        )
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Custom provider not found")

    _validate_url_no_ssrf(cp.base_url)

    api_key = auth_utils.decrypt_api_key(cp.api_key)
    url = f"{cp.base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    except httpx.TimeoutException:
        return DiscoverModelsResponse(models=[], discovery_supported=False, error="Request timed out")
    except httpx.RequestError as exc:
        return DiscoverModelsResponse(models=[], discovery_supported=False, error=str(exc))

    # Treat 404/405 as "endpoint not supported" rather than an error
    if response.status_code in {404, 405}:
        return DiscoverModelsResponse(models=[], discovery_supported=False)

    if response.status_code >= 400:
        return DiscoverModelsResponse(
            models=[],
            discovery_supported=False,
            error=f"HTTP {response.status_code}: {response.text[:200]}",
        )

    try:
        data = response.json()
        model_ids: list[str] = [
            item["id"] for item in data.get("data", []) if isinstance(item, dict) and "id" in item
        ]
        model_ids = model_ids[:_MAX_DISCOVERED_MODELS]
    except Exception as exc:  # noqa: BLE001
        return DiscoverModelsResponse(
            models=[], discovery_supported=True, error=f"Failed to parse response: {exc}"
        )

    return DiscoverModelsResponse(models=model_ids, discovery_supported=True)
