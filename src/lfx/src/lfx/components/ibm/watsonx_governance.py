import json
import traceback

import requests

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import SecretStrInput, StrInput
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data


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
            info="The base endpoint URL (e.g., https://us-south.ml.cloud.ibm.com)",
            required=True,
        ),
        StrInput(
            name="deployment_id",
            display_name="Deployment ID",
            info="The ID of your deployment",
            required=True,
        ),
        StrInput(
            name="prompt_variables",
            display_name="Prompt Variables",
            required=True,
            info="Prompt variables as JSON object with SEARCH_CHUNKS and USER_QUERY",
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
        except Exception as e:
            logger.exception("Error getting token: " + str(e))
            raise

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

        # Parse prompt_variables if it's a string
        if isinstance(self.prompt_variables, str):
            try:
                prompt_vars = json.loads(self.prompt_variables)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in prompt_variables: {e!s}"
                logger.error(error_msg)
                return Data(text=error_msg, data={"error": str(e), "success": False})
        else:
            prompt_vars = self.prompt_variables

        # Construct the payload - this matches the curl example
        payload = {"parameters": {"prompt_variables": prompt_vars}}

        # Construct endpoint URL with deployment_id
        base_url = self.endpoint_url.rstrip("/")
        endpoint = f"{base_url}/ml/v1/deployments/{self.deployment_id}/text/generation?version=2021-05-01"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {iam_token}",
        }

        logger.info(f"Sending request to: {endpoint}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)

            # Log response details for debugging
            logger.info(f"Response status: {response.status_code}")

            response.raise_for_status()

            try:
                body = response.json()
                body_text = json.dumps(body, indent=2)
            except ValueError:
                body = response.text
                body_text = body

            logger.info("Payload logged with Governance")
            return Data(text=body_text, data=body)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e!s}"
            response_body = response.text if "response" in locals() else "No response body"
            logger.error(error_msg)
            logger.error(f"Response body: {response_body}")
            logger.error(traceback.format_exc())
            return Data(
                text=f"{error_msg}\nResponse: {response_body}",
                data={"error": str(e), "response": response_body, "success": False},
            )

        except json.JSONDecodeError as e:
            error_msg = f"Error parsing JSON payload: {e!s}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return Data(text=error_msg, data={"error": str(e), "success": False})

        except Exception as e:  # noqa: BLE001
            error_msg = f"Error logging payload to watsonx.governance: {e!s}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return Data(text=error_msg, data={"error": str(e), "success": False})
