from permit import Permit

from langflow.custom import Component
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.schema.message import Message
from langflow.template import Output


class DataProtectionComponent(Component):
    display_name = "Data Protection"
    description = "Gets allowed resource IDs for a user."
    icon = "shield"

    inputs = [
        MessageTextInput(
            name="user_id",
            display_name="User ID",
            required=True,
            info="The ID of the user to retrieve permissions for",
        ),
        MessageTextInput(
            name="action",
            display_name="Action",
            required=True,
            info="The action to filter permissions by (e.g., read)",
        ),
        MessageTextInput(
            name="resource_type",
            display_name="Resource Type",
            required=True,
            info="The type of resource to filter (e.g., document)",
        ),
        MessageTextInput(
            name="pdp_url",
            display_name="PDP URL",
            required=True,
            value="https://cloudpdp.api.permit.io",
            info="URL of the Policy Decision Point",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            value="test-key",
            info="API Key for authenticating with the Permit PDP",
        ),
    ]
    outputs = [
        Output(display_name="Allowed IDs", name="allowed_ids", method="validate_auth"),
    ]

    async def validate_auth(self) -> Message:
        permit = Permit(token=self.api_key, pdp=self.pdp_url)
        permissions = await permit.get_user_permissions(self.user_id)
        allowed_ids = [
            p.resource_id for p in permissions if p.resource == self.resource_type and p.action == self.action
        ]
        return Message(content=allowed_ids)
