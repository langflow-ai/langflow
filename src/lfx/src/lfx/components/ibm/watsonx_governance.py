import json
import traceback

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson_openscale import APIClient
from ibm_watson_openscale.data_sets import DataSetTypes, TargetTypes
from ibm_watson_openscale.supporting_classes.payload_record import PayloadRecord

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    BoolInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from lfx.io import Output
from lfx.log.logger import logger
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
            info="The API Key to connect to your IBM Cloud Account",
        ),
        StrInput(
            name="instance_url",
            display_name="Watsonx.Gov Service URL",
            info="The Service URL of your Watsonx.Governance Instance",
            required=True,
        ),
        StrInput(
            name="service_instance_id",
            display_name="Service Instance ID",
            info="The ID of the Watsonx.Governance Instance to connect to",
            required=True,
        ),
        MessageTextInput(
            name="payload", display_name="Payload", required=True, info="Payload to be logged with Watsonx.Governance"
        ),
        BoolInput(
            name="include_user_prompt_flag",
            display_name="Include User Prompt",
            required=True,
            info="Determine whether to include the user's prompt in the payload",
        ),
        MessageTextInput(
            name="user_prompt", display_name="User Prompt", required=False, info="Prompt used to generate response"
        ),
    ]

    outputs = [Output(name="gov_response", display_name="Watsonx.Governance Response", method="execute_call")]

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
        """Execute the governance logging call to watsonx.governance.

        Returns:
            Data object containing the result of the governance logging operation.
        """
        try:
            # Step 1: Initialize authenticator and client
            authenticator = IAMAuthenticator(apikey=self.api_key, url="https://iam.cloud.ibm.com/identity/token")

            wos_client = APIClient(
                authenticator=authenticator, service_instance_id=self.service_instance_id, service_url=self.service_url
            )

            logger.info("Successfully initialized Watson OpenScale client")

            # Step 2: Get payload logging dataset ID
            payload_logging_data_set_id = (
                wos_client.data_sets.list(
                    type=DataSetTypes.PAYLOAD_LOGGING,
                    target_target_id=self.subscription_id,
                    target_target_type=TargetTypes.SUBSCRIPTION,
                )
                .result.data_sets[0]
                .metadata.id
            )

            logger.info(f"Using dataset ID: {payload_logging_data_set_id}")

            # Step 3: Parse request and response data
            request_data = json.loads(self.request_data) if isinstance(self.request_data, str) else self.request_data
            response_data = (
                json.loads(self.response_data) if isinstance(self.response_data, str) else self.response_data
            )

            logger.info(f"Request data: {request_data}")
            logger.info(f"Response data: {response_data}")

            # Step 4: Store payload record
            wos_client.data_sets.store_records(
                data_set_id=payload_logging_data_set_id,
                request_body=[
                    PayloadRecord(request=request_data, response=response_data, response_time=self.response_time)
                ],
            )

            logger.info("Watson OpenScale payload logged successfully.")

            result = {
                "success": True,
                "dataset_id": payload_logging_data_set_id,
                "message": "Payload logged successfully to watsonx.governance",
            }

            return Data(text=json.dumps(result, indent=2), data=result)

        except IndexError:
            error_msg = "No payload logging dataset found for the given subscription ID"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return Data(text=error_msg, data={"error": error_msg, "success": False})

        except json.JSONDecodeError as e:
            error_msg = f"Error parsing JSON payload: {e!s}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return Data(text=error_msg, data={"error": str(e), "success": False})

        except Exception as e:  # noqa: BLE001 - Catch-all for unexpected errors during governance logging
            error_msg = f"Error logging payload to watsonx.governance: {e!s}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return Data(text=error_msg, data={"error": str(e), "success": False})
