from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    BoolInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from lfx.io import Output
from lfx.schema.data import Data


# from lfx.io import Input, Output
class WatsonxGovernanceComponent(Component):
    """A component that logs generative AI payloads to IBM watsonx.governance for tracking and compliance."""

    display_name: str = "IBM watsonx.governance"
    description: str = "Logs AI model payloads to IBM watsonx.governance for tracking, auditing, and compliance."
    icon: str = "WatsonxAI"
    name: str = "WatsonxGovernance"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Watsonx API Key",
            required=True,
            info="The API Key to connect to your IBM Cloud Account"
        ),
        StrInput(
            name="instance_url",
            display_name="Watsonx.Gov Service URL",
            info="The Service URL of your Watsonx.Governance Instance",
            required=True
        ),
        StrInput(
            name="service_instance_id",
            display_name="Service Instance ID",
            info="The ID of the Watsonx.Governance Instance to connect to",
            required=True
        ),
        MessageTextInput(
            name="payload",
            display_name="Payload",
            required=True,
            info="Payload to be logged with Watsonx.Governance"
        ),
        BoolInput(
            name="include_user_prompt_flag",
            display_name="Include User Prompt",
            required=True,
            info="Determine whether to include the user's prompt in the payload"
        ),
        MessageTextInput(
            name="user_prompt",
            display_name="User Prompt",
            required=False,
            info="Prompt used to generate response"
        )
    ]

    outputs = [
        Output(
            name="gov_response",
            display_name="Watsonx.Governance Response",
            method="execute_call"
        )
    ]

    def update_build_config(self, build_config: dict, field_name: str, field_value: str | None = None) -> dict:
        """Update build configuration.

        Args:
            build_config: The build configuration dictionary
            field_name: Name of the field to update
            field_value: Value to set for the field (optional)

        Returns:
            Updated build configuration dictionary
        """
        if field_value is not None:
            build_config[field_name] = field_value
        return build_config

    async def execute_call(self) -> Data:
        """Execute the main governance. I believe this is where we actually do the API call to governance.

        Returns:
            Data object containing the result of the governance call..?
            we can leave this as None i think if theres no return??.
        """
        result = ""  # TODO: Implement actual logic
        return Data(text=str(result), data=result)
