from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from lfx.log.logger import logger
from lfx.services.settings.feature_flags import FEATURE_FLAGS

if TYPE_CHECKING:
    from contextvars import Token
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DeploymentAdapterContext:
    provider_id: UUID


class DeploymentProviderIDContext:
    _current: ClassVar[ContextVar[DeploymentAdapterContext | None]] = ContextVar(
        "langflow_current_deployment_context",
        default=None,
    )

    @classmethod
    def get_current(cls) -> DeploymentAdapterContext | None:
        return cls._current.get()

    @classmethod
    def set_current(cls, context: DeploymentAdapterContext) -> Token[DeploymentAdapterContext | None]:
        return cls._current.set(context)

    @classmethod
    def reset_current(cls, token: Token[DeploymentAdapterContext | None]) -> None:
        cls._current.reset(token)

    @classmethod
    @contextmanager
    def scope(cls, context: DeploymentAdapterContext):
        token: Token[DeploymentAdapterContext | None] = cls.set_current(context)
        try:
            yield
        finally:
            cls.reset_current(token)


@contextmanager
def deployment_provider_scope(provider_id: UUID):
    """Set deployment provider context for a scoped adapter call.

    Owns the lifetime of adapter-level per-scope state so sequential/nested
    scopes cannot poison each other. Today that state is the WxO client
    ownership assertion, composed in directly.

    Multi-adapter extension: when a second adapter is added, accept
    ``provider_key`` here and dispatch to the matching adapter's scope
    (if/else on ``provider_key``, or a keyed registry — either works).
    """
    adapter_context = DeploymentAdapterContext(provider_id=provider_id)

    if not FEATURE_FLAGS.wxo_deployments:
        logger.debug("Skipping deployment adapter scope setup: wxo_deployments feature flag disabled")
        with DeploymentProviderIDContext.scope(adapter_context):
            yield
        return

    try:
        from langflow.services.adapters.deployment.watsonx_orchestrate.client import (
            wxo_scope,
        )
    except ModuleNotFoundError as exc:
        logger.info("Skipping Watsonx Orchestrate deployment scope setup: %s", exc)
        with DeploymentProviderIDContext.scope(adapter_context):
            yield
        return

    with (
        DeploymentProviderIDContext.scope(adapter_context),
        wxo_scope(),
    ):
        yield
