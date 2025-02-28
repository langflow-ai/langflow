from permit import Permit

from langflow.custom import Component
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.schema.message import Message
from langflow.template import Output


class PermissionsCheckComponent(Component):
    display_name = "Permissions Check"
    description = "Checks if a user is allowed an action on a resource, with separate outputs for allowed and denied."
    icon = "check"

    inputs = [
        MessageTextInput(
            name="user_id",
            display_name="User ID",
            required=True,
            info="The ID of the user to check permissions for",
        ),
        MessageTextInput(
            name="action",
            display_name="Action",
            required=True,
            info="The action to check (e.g., read, write)",
        ),
        MessageTextInput(
            name="resource",
            display_name="Resource",
            required=True,
            info="The resource to check access for (e.g., document-1)",
        ),
        MessageTextInput(
            name="tenant",
            display_name="Tenant",
            required=False,
            info="The tenant ID for multi-tenancy (optional)",
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
        Output(display_name="Allowed", name="allowed", method="allowed_result"),
        Output(display_name="Denied", name="denied", method="denied_result"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._permission_result = False

    async def validate_auth(self) -> bool:
        permit = Permit(token=self.api_key, pdp=self.pdp_url)
        context = {"tenant": self.tenant} if hasattr(self, "tenant") and self.tenant else {}

        # Get the result from permit service
        self._permission_result = await permit.check(self.user_id, self.action, self.resource, context=context)
        return self._permission_result

    def allowed_result(self) -> Message:
        if self._permission_result:
            return Message(content=f"Permission granted for {self.user_id} to {self.action} on {self.resource}")
        return Message(content="")

    def denied_result(self) -> Message:
        if not self._permission_result:
            return Message(content=f"Permission denied for {self.user_id} to {self.action} on {self.resource}")
        return Message(content="")
