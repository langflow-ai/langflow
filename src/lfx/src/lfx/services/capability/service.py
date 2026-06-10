"""Capability service for pluggable execution policy."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.capability.defaults import AllTrustedClassifier, NoopCapabilityProvider, SingleTenantResolver
from lfx.services.capability.protocols import (
    CapabilityContext,
    CapabilityProvider,
    RoutingDecision,
    TenantResolver,
    Trust,
    TrustClassifier,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from lfx.services.settings.service import SettingsService


ENTRY_POINT_GROUP = "lfx.capability_providers"


class CapabilityService(Service):
    """Holds the active capability provider, trust classifier, and tenant resolver."""

    name = "capability_service"

    def __init__(self, settings_service: SettingsService) -> None:
        super().__init__()
        self._settings_service = settings_service
        self._provider: CapabilityProvider = NoopCapabilityProvider()
        self._classifier: TrustClassifier = AllTrustedClassifier()
        self._resolver: TenantResolver = SingleTenantResolver()
        self._untrusted_executor_kind: str | None = None
        self._discover_entry_points()

    def install(
        self,
        *,
        provider: CapabilityProvider | None = None,
        classifier: TrustClassifier | None = None,
        resolver: TenantResolver | None = None,
        untrusted_executor_kind: str | None = None,
    ) -> None:
        """Replace one or more capability primitives."""
        if provider is not None:
            self._provider = provider
        if classifier is not None:
            self._classifier = classifier
        if resolver is not None:
            self._resolver = resolver
        if untrusted_executor_kind is not None:
            self._untrusted_executor_kind = untrusted_executor_kind

    @property
    def provider(self) -> CapabilityProvider:
        return self._provider

    @property
    def classifier(self) -> TrustClassifier:
        return self._classifier

    @property
    def resolver(self) -> TenantResolver:
        return self._resolver

    @property
    def is_passthrough(self) -> bool:
        """True when the service is still using inert defaults."""
        return (
            isinstance(self._provider, NoopCapabilityProvider)
            and isinstance(self._classifier, AllTrustedClassifier)
            and isinstance(self._resolver, SingleTenantResolver)
            and self._untrusted_executor_kind is None
        )

    def route(
        self,
        graph: Any,
        *,
        user_id: str | None = None,
        flow_id: str | None = None,
        run_id: str | None = None,
        default_executor_kind: str = "in-process",
        scopes: Sequence[str] | None = None,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> RoutingDecision:
        """Return the executor and capability metadata for one graph run."""
        context = CapabilityContext(
            graph=graph,
            user_id=user_id,
            flow_id=flow_id,
            run_id=run_id,
            runtime_options=runtime_options or {},
        )
        tenant_id = self._resolver.resolve(context)
        trust = self._classifier.trust_of_flow(context)
        executor_kind = default_executor_kind
        if trust is Trust.UNTRUSTED and self._untrusted_executor_kind is not None:
            executor_kind = self._untrusted_executor_kind

        effective_scopes = tuple(scopes or ())
        token = self._provider.mint(
            context=context,
            tenant_id=tenant_id,
            component_id=None,
            scopes=effective_scopes,
        )
        options: dict[str, Any] = {}
        if token:
            options["lfx_capability_token"] = token
        if not self.is_passthrough:
            options["lfx_tenant_id"] = tenant_id
            options["lfx_trust"] = trust.value

        return RoutingDecision(
            executor_kind=executor_kind,
            tenant_id=tenant_id,
            trust=trust,
            capability_token=token,
            scopes=effective_scopes,
            runtime_options=options,
        )

    def _discover_entry_points(self) -> None:
        """Discover capability primitives shipped by installed packages."""
        try:
            eps = entry_points(group=ENTRY_POINT_GROUP)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to enumerate entry points for group=%r. Capability discovery skipped.",
                ENTRY_POINT_GROUP,
            )
            return

        for ep in eps:
            try:
                obj = ep.load()
                config = obj() if callable(obj) else obj
                if not isinstance(config, dict):
                    logger.warning(
                        "Capability entry point %r did not return a dict; got %r",
                        ep.name,
                        type(config).__name__,
                    )
                    continue
                self.install(**config)
                logger.debug("Installed capability primitives from entry point: %s", ep.name)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to load capability entry point %s", ep.name)

    async def teardown(self) -> None:
        """Reset to pass-through defaults and re-run plugin discovery."""
        self._provider = NoopCapabilityProvider()
        self._classifier = AllTrustedClassifier()
        self._resolver = SingleTenantResolver()
        self._untrusted_executor_kind = None
        self._discover_entry_points()
