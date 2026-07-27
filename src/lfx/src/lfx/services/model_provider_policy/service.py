"""Default OSS model-provider policy (allow all)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.model_provider_policy.base import BaseModelProviderPolicyService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection

    from lfx.services.model_provider_policy.base import ModelProviderPolicyContext, ModelProviderPolicyPurpose


@register_service(ServiceType.MODEL_PROVIDER_POLICY_SERVICE)
class ModelProviderPolicyService(BaseModelProviderPolicyService):
    """OSS default that preserves the historical allow-all behavior."""

    def __init__(self) -> None:
        super().__init__()
        self.set_ready()
        logger.debug("Model provider policy service initialized (allow all)")

    @property
    def name(self) -> str:
        return ServiceType.MODEL_PROVIDER_POLICY_SERVICE.value

    def get_allowed_provider_ids(
        self,
        *,
        context: ModelProviderPolicyContext,  # noqa: ARG002
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,  # noqa: ARG002
    ) -> Collection[str]:
        return candidate_provider_ids
