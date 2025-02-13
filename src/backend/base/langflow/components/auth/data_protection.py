from permit import Permit

from langflow.base.auth.model import AuthComponent
from langflow.io import StrInput
from langflow.template import Output


class DataProtectionComponent(AuthComponent):
    """Component for retrieving allowed resource IDs for a user."""

    display_name = "Data Protection"
    description = "Retrieves allowed resource IDs for a user using Permit.io"
    documentation = "https://docs.langflow.org/components-auth"
    icon = "shield"

    inputs = [
        StrInput(
            name="user_id",
            display_name="User ID",
            required=True,
            info="User identifier"
        ),
        StrInput(
            name="action",
            display_name="Action",
            required=True,
            info="Action to check (e.g., 'read', 'write')"
        ),
        StrInput(
            name="resource_type",
            display_name="Resource Type",
            required=True,
            info="Type of resource to check permissions for"
        ),
        StrInput(
            name="filter_ids",
            display_name="Filter IDs",
            field_type="list",
            required=False,
            info="Optional list of specific IDs to check permissions for"
        )
    ]

    outputs = [
        Output(display_name="Allowed IDs", name="auth_result", method="validate_auth")
    ]

    def build_config(self) -> dict:
        """Return configuration options for the component."""
        return {
            "pdp_url": {
                "display_name": "PDP URL",
                "description": "URL of the Policy Decision Point",
                "type": "str",
                "required": True,
            },
            "api_key": {
                "display_name": "API Key",
                "description": "Permit.io API key",
                "type": "str",
                "required": True,
            }
        }

    def build(self, pdp_url: str, api_key: str) -> None:
        """Initialize the Permit client."""
        self.permit = Permit(
            pdp=pdp_url,
            token=api_key
        )

    def validate_auth(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        filter_ids: list[str] | None = None
    ) -> list[str]:
        """Get list of resource IDs the user has permission to access.

        If filter_ids is provided, filters that list instead of fetching all permissions.

        Args:
            user_id: User identifier
            action: Action to check
            resource_type: Type of resource
            filter_ids: Optional list of IDs to filter

        Returns:
            List[str]: List of allowed resource IDs

        Raises:
            ValueError: If permission check fails
        """
        allowed_ids = []
        try:
            if filter_ids is not None:
                # Filter provided IDs using filter_objects
                objects = [{"id": id_} for id_ in filter_ids]
                filtered = self.permit.filter_objects(
                    user=user_id,
                    objects=objects,
                    action=action,
                    resource_type=resource_type
                )
                allowed_ids = [obj["id"] for obj in filtered]
            else:
                # Get all permissions and filter by action
                permissions = self.permit.get_user_permissions(
                    user=user_id,
                    resource_type=resource_type
                )
                allowed_ids = [
                    perm.resource_id
                    for perm in permissions
                    if perm.action == action
                ]
        except Exception as exc:
            error_msg = f"Failed to get user permissions: {exc}"
            raise ValueError(error_msg) from exc

        self.status = allowed_ids
        return allowed_ids
