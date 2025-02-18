from typing import Any

from permit import Permit

from langflow.base.auth.error_constants import AuthErrors
from langflow.base.auth.model import AuthComponent
from langflow.io import MessageTextInput, SecretStrInput
from langflow.template import Output


class DataProtectionComponent(AuthComponent):
    """Component for retrieving allowed resource IDs for a user."""

    display_name = "Data Protection"
    description = "Retrieves allowed resource IDs for a user using Permit.io"
    documentation = "https://docs.langflow.org/components-auth"
    icon = "shield"

    outputs = [Output(display_name="Allowed IDs", name="auth_result", method="validate_auth")]

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
        MessageTextInput(
            name="resource_type",
            display_name="Resource Type",
            required=True,
            info="Type of resource to check permissions for",
            input_types=["Text"],
        ),
        MessageTextInput(
            name="filter_ids",
            display_name="Filter IDs",
            field_type="list",
            required=False,
            info="Optional list of specific IDs to check permissions for",
        ),
        MessageTextInput(
            name="sensitive_fields",
            display_name="Sensitive Fields",
            field_type="list",
            required=False,
            info="List of fields to redact from response",
        ),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.permit: Permit | None = None

    def build(self, **kwargs: Any) -> None:
        """Initialize the Permit client."""
        pdp_url = kwargs.get("pdp_url") or getattr(self, "pdp_url", None)
        api_key = kwargs.get("api_key") or getattr(self, "api_key", None)

        if pdp_url and api_key:
            self.permit = Permit(pdp=pdp_url, token=api_key)

    async def _get_allowed_ids(self, filter_ids: list[str] | None) -> list[str]:
        """Helper method to get allowed IDs based on filters."""
        if not self.permit:
            error = AuthErrors.PERMIT_NOT_INITIALIZED
            raise ValueError(error.message)

        if filter_ids is not None:
            objects = [{"id": id_} for id_ in filter_ids]
            filtered = await self.permit.filter_objects(
                user=self.user_id, objects=objects, action=self.action, resource=self.resource_type
            )
            return [obj["id"] for obj in filtered]

        permissions = await self.permit.get_user_permissions(user=self.user_id)
        return [
            perm.resource_id
            for perm in permissions
            if perm.resource == self.resource_type and perm.action == self.action
        ]

    async def validate_auth(self, **kwargs: Any) -> list[str]:
        """Get list of resource IDs the user has permission to access."""
        if not self.permit:
            self.build(pdp_url=getattr(self, "pdp_url", None), api_key=getattr(self, "api_key", None))
            if not self.permit:
                error = AuthErrors.PERMIT_NOT_INITIALIZED
                raise ValueError(error.message)

        result: list[str] = []
        try:
            filter_ids = kwargs.get("filter_ids") or getattr(self, "filter_ids", None)
            allowed_ids = await self._get_allowed_ids(filter_ids)
            if allowed_ids:
                result = allowed_ids

        except Exception as exc:
            error = AuthErrors.validation_failed(exc)
            raise ValueError(error.message) from exc

        self.status = result
        return result
