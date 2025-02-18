from typing import Any

from permit import Permit

from langflow.base.auth.error_constants import AuthErrors
from langflow.base.auth.model import AuthComponent
from langflow.io import MessageTextInput, SecretStrInput
from langflow.template import Output


class PermissionsCheckComponent(AuthComponent):
    """Component for performing authorization checks."""

    display_name = "Permissions Check"
    description = "Performs authorization checks using Permit.io"
    documentation = "https://docs.langflow.org/components-auth"
    icon = "lock"

    outputs = [
        Output(display_name="Allowed Path", name="allowed", method="get_allowed"),
        Output(display_name="Denied Path", name="denied", method="get_denied"),
    ]

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Permit.io API Key",
            required=True,
            info="Your Permit.io API key",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="pdp_url",
            display_name="PDP URL",
            required=True,
            value="https://cloudpdp.api.permit.io",
            info="URL of the Policy Decision Point",
        ),
        MessageTextInput(
            name="user_id", display_name="User ID", required=True, info="User identifier", input_types=["Text"]
        ),
        MessageTextInput(name="action", display_name="Action", required=True),
        MessageTextInput(name="resource", display_name="Resource", required=True),
        MessageTextInput(name="tenant", display_name="Tenant", required=False),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.permit: Permit | None = None

    @staticmethod
    def evaluate_access(granted: str) -> str:
        """Handle conditional logic based on access grant status."""
        if granted:
            return "proceed"
        return "error: Access denied for this resource"

    def build(self, **kwargs: Any) -> None:
        """Initialize the Permit client."""
        pdp_url = kwargs.get("pdp_url") or getattr(self, "pdp_url", None)
        api_key = kwargs.get("api_key") or getattr(self, "api_key", None)

        if pdp_url and api_key:
            self.permit = Permit(pdp=pdp_url, token=api_key)

    async def validate_auth(self) -> bool:
        """Validate authorization for the current request."""
        if not self.permit:
            self.build(pdp_url=getattr(self, "pdp_url", None), api_key=getattr(self, "api_key", None))
            if not self.permit:
                error = AuthErrors.PERMIT_NOT_INITIALIZED
                raise ValueError(error.message)

        try:
            context = {"tenant": self.tenant} if hasattr(self, "tenant") else {}
            allowed = await self.permit.check(
                user=self.user_id, action=self.action, resource=self.resource, context=context
            )
            self.status = bool(allowed)
            return bool(allowed)

        except Exception as exc:
            error = AuthErrors.validation_failed(exc)
            raise ValueError(error.message) from exc

    async def get_allowed(self) -> bool:
        """Return True if permission was granted."""
        return await self.validate_auth()

    async def get_denied(self) -> bool:
        """Return True if permission was denied."""
        return not await self.validate_auth()
