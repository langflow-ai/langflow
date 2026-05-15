"""Capability-backed VariableService for lfx.

Replaces lfx's default in-memory / env-fallback variable service. Every
`get_variable(name, ...)` call goes to the prototype's Runtime API with a
run token. The token's scopes determine what is reachable. The worker (or
the lfx process registering this service) never holds the DB.

Registration is via lfx's @register_service decorator, applied when this
module is imported.
"""

from __future__ import annotations

import os

import httpx
from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.registry import register_service
from lfx.services.schema import ServiceType


class _RuntimeAPIConfig:
    """Read RUNTIME_API_URL + RUN_TOKEN once at instantiation time.

    The token is supplied by the orchestrator that boots lfx. In Phase A,
    that orchestrator is `scripts/run_basic_prompting_lfx.py`. In a real
    Stepflow-shaped deployment, the worker process would receive these via
    env from the control plane.
    """

    def __init__(self) -> None:
        self.base_url = os.environ["MT_RUNTIME_API_URL"].rstrip("/")
        self.token = os.environ["MT_RUN_TOKEN"]


@register_service(ServiceType.VARIABLE_SERVICE)
class CapabilityVariableService(Service):
    name = "variable_service"

    def __init__(self) -> None:
        super().__init__()
        try:
            self._config: _RuntimeAPIConfig | None = _RuntimeAPIConfig()
        except KeyError:
            # Tests / non-prototype usage: fall back to None and let calls error
            # if anyone actually hits the service without configuration.
            self._config = None
        self._client = httpx.AsyncClient(timeout=10.0)
        self.set_ready()
        logger.debug("CapabilityVariableService registered")

    async def get_variable(self, name: str, **kwargs) -> str | None:  # noqa: ARG002
        """Fetch the variable through the Runtime API.

        Signature absorbs `user_id`, `field`, `session` kwargs from the
        langflow call path. We don't use them here — capability scoping
        happens through the token, not through the kwargs.
        """
        if self._config is None:
            msg = (
                "CapabilityVariableService called without MT_RUNTIME_API_URL "
                "and MT_RUN_TOKEN set. The prototype orchestrator is "
                "responsible for setting these before lfx starts."
            )
            raise RuntimeError(msg)
        url = f"{self._config.base_url}/runtime/variables/{name}"
        r = await self._client.get(url, headers={"Authorization": f"Bearer {self._config.token}"})
        if r.status_code == 200:
            logger.debug(f"variable '{name}' resolved through capability service")
            return r.json()["value"]
        if r.status_code in (401, 403):
            # Surface as a clear, actionable error. Langflow would otherwise
            # mask this as "variable not found".
            msg = f"capability denied for variables:read:{name}: {r.text}"
            raise PermissionError(msg)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return None

    def set_variable(self, name: str, value: str, **kwargs) -> None:
        # The capability boundary doesn't expose variable writes to workers
        # in this prototype. Authoring writes happen in the control plane.
        msg = "set_variable is not supported in the capability-backed tier"
        raise NotImplementedError(msg)

    async def get_all_decrypted_variables(self, user_id, session) -> dict[str, str]:  # noqa: ARG002
        # Not implemented: enumerating all of a tenant's variables in the
        # worker tier is exactly the kind of broad read the design refuses.
        return {}

    async def teardown(self) -> None:
        await self._client.aclose()
