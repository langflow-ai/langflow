import json
import traceback
from typing import Any

import requests

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import SecretStrInput, StrInput
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
            name="endpoint_url",
            display_name="Deployment endpoint URL",
            info="The endpoint of your deployed prompt template ",
            required=True,
        ),
        StrInput(
            name="deployment_id",
            display_name="Deployment ID",
            info="The ID of your deployment",
            required=False,
        ),
        StrInput(
            name="prompt_variables",
            display_name="Prompt Variables",
            required=True,
            info="Prompt variables to be passed to your deployed endpoint. Enter in format",
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

    def get_token(self) -> str:
        try:
            iam_url = "https://iam.cloud.ibm.com/identity/token"
            token_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            token_data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.api_key}

            token_response = requests.post(iam_url, headers=token_headers, data=token_data, timeout=10)
            token_response.raise_for_status()
            return token_response.json()["access_token"]
        except Exception as e:  # noqa: BLE001
            logger.exception("Error getting token: " + str(e))

    def execute_call(self) -> Data:
        """Execute the governance logging call to watsonx.governance.

        Returns:
            Data object containing the result of the governance logging operation.
        """
        try:
            iam_token = self.get_token()
        except Exception as e:  # noqa: BLE001
            msg = f"Failed to obtain IAM token: {e!s}"
            logger.error(msg)
            logger.error(traceback.format_exc())
            return Data(text=msg, data={"error": str(e), "success": False})

        endpoint = self.endpoint_url

        prompt_vars: dict[str, Any] = self.prompt_variables

        payload = {"parameters": {"prompt_variables": prompt_vars}}

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {iam_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            try:
                body = response.json()
                body_text = json.dumps(body, indent=2)
            except ValueError:
                body = response.text
                body_text = body

            logger.info("Payload logged with Governance")
            return Data(text=body_text, data=body)

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

    # async def execute_call(self) -> Data:
    #     """Execute the governance logging call to watsonx.governance.

    #     Returns:
    #         Data object containing the result of the governance logging operation.
    #     """
    #     try:
    #         # Step 1: Initialize authenticator and client
    #         authenticator = IAMAuthenticator(apikey=self.api_key, url="https://iam.cloud.ibm.com/identity/token")

    #         wos_client = APIClient(
    #             authenticator=authenticator, service_instance_id=self.deployment_id, service_url=self.endpoint_url
    #         )

    #         logger.info("Successfully initialized Watson OpenScale client")

    #         # Step 2: Get payload logging dataset ID
    #         payload_logging_data_set_id = (
    #             wos_client.data_sets.list(
    #                 type=DataSetTypes.PAYLOAD_LOGGING,
    #                 target_target_id=self.deployment_id,
    #                 target_target_type=TargetTypes.SUBSCRIPTION,
    #             )
    #             .result.data_sets[0]
    #             .metadata.id
    #         )

    #         logger.info(f"Using dataset ID: {payload_logging_data_set_id}")

    #         # Step 3: Parse request and response data
    #         request_data = json.loads(self.prompt_variables) if isinstance(self.prompt_variables, str) else self.prompt_variables  # noqa: E501

    #         logger.info(f"Request data: {request_data}")

    #         # Step 4: Store payload record
    #         wos_client.data_sets.store_records(
    #             data_set_id=payload_logging_data_set_id,
    #             request_body=[
    #                 PayloadRecord(request=request_data, response_time=self.response_time)
    #             ],
    #         )

    #         logger.info("Watson OpenScale payload logged successfully.")

    #         result = {
    #             "success": True,
    #             "dataset_id": payload_logging_data_set_id,
    #             "message": "Payload logged successfully to watsonx.governance",
    #         }

    #         return Data(text=json.dumps(result, indent=2), data=result)

    #     except IndexError:
    #         error_msg = "No payload logging dataset found for the given subscription ID"
    #         logger.error(error_msg)
    #         logger.error(traceback.format_exc())
    #         return Data(text=error_msg, data={"error": error_msg, "success": False})

    #     except json.JSONDecodeError as e:
    #         error_msg = f"Error parsing JSON payload: {e!s}"
    #         logger.error(error_msg)
    #         logger.error(traceback.format_exc())
    #         return Data(text=error_msg, data={"error": str(e), "success": False})

    #     except Exception as e:
    #         error_msg = f"Error logging payload to watsonx.governance: {e!s}"
    #         logger.error(error_msg)
    #         logger.error(traceback.format_exc())
    #         return Data(text=error_msg, data={"error": str(e), "success": False})
