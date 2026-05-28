"""List-endpoint filter for authorization checks (batched enforce)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from langflow.services.authorization.actions import FlowAction
from langflow.services.authorization.guards import _auth_context, _coerce_action
from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from langflow.services.database.models.user.model import User, UserRead


T = TypeVar("T")


def _default_resource_id_getter(item: Any) -> UUID:
    """Default key extractor used by filter_visible_resources."""
    return item.id


async def filter_visible_resources(
    user: User | UserRead,
    *,
    resource_type: str,
    candidates: list[T],
    key: Callable[[T], UUID] | None = None,
    domain: str = "*",
    domain_extractor: Callable[[T], str] | None = None,
    owner_extractor: Callable[[T], UUID | None] | None = None,
    act: FlowAction | str = FlowAction.READ,
) -> list[T]:
    """Return candidates the user may read (no-op when AUTHZ_ENABLED is false)."""
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED or not candidates:
        return candidates

    extractor = key if key is not None else _default_resource_id_getter
    authz = get_authorization_service()
    act_str = _coerce_action(act)
    user_id = getattr(user, "id", None)

    # Owned rows skip batch_enforce (matches direct-read owner override).
    owned_indices: set[int] = set()
    enforce_indices: list[int] = []
    enforce_items: list[T] = []
    for index, item in enumerate(candidates):
        if owner_extractor is not None and user_id is not None and owner_extractor(item) == user_id:
            owned_indices.add(index)
        else:
            enforce_indices.append(index)
            enforce_items.append(item)

    decisions: list[bool] = [False] * len(candidates)
    for index in owned_indices:
        decisions[index] = True

    if enforce_items:
        if domain_extractor is None:
            # Single-domain batch_enforce.
            requests = [(f"{resource_type}:{extractor(item)}", act_str) for item in enforce_items]
            results = await authz.batch_enforce(
                user_id=user_id,
                domain=domain,
                requests=requests,
                context=_auth_context(user),
            )
            for original_index, allowed in zip(enforce_indices, results, strict=True):
                decisions[original_index] = allowed
        else:
            # One batch_enforce per resolved domain.
            buckets: dict[str, list[tuple[int, T]]] = {}
            for original_index, item in zip(enforce_indices, enforce_items, strict=True):
                buckets.setdefault(domain_extractor(item), []).append((original_index, item))

            auth_context = _auth_context(user)
            for resolved_domain, bucket in buckets.items():
                bucket_requests = [(f"{resource_type}:{extractor(item)}", act_str) for _, item in bucket]
                bucket_results = await authz.batch_enforce(
                    user_id=user_id,
                    domain=resolved_domain,
                    requests=bucket_requests,
                    context=auth_context,
                )
                for (original_index, _), allowed in zip(bucket, bucket_results, strict=True):
                    decisions[original_index] = allowed

    return [item for item, allowed in zip(candidates, decisions, strict=True) if allowed]
