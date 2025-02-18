from urllib.parse import urljoin

import httpx

from langflow.custom import Component
from langflow.inputs import MessageTextInput, SecretStrInput, StrInput
from langflow.schema import Data
from langflow.template import Output


class ThoughtSpotQueryComponent(Component):
    display_name = "ThoughtSpot Query"
    description = (
        "Perform analytics queries on tabular data, tool will convert natural"
        " language to SQL and output a csv result. Assume source data is already provided."
    )
    icon = "ThougtSpot"

    inputs = [
        StrInput(
            name="instance_url",
            display_name="ThoughtSpot Instance endpoint",
            info="Enter your ThoughtSpot URL"
        ),
        SecretStrInput(
            name="api_key",
            display_name="ThoughtSpot API Key",
            info="Enter your API Key"
        ),
        StrInput(
            name="model_id",
            display_name="Data Model to query",
            info="ThoughtSpot Model Id"
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Question in natural language like 'sales by product'.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process_inputs", type_=Data),
    ]

    async def process_inputs(self) -> Data:
        """Process the Query and return CSV formatted data as a string.

        Returns:
            Data: A Data object containing CSV formatted information.
        """
        try:
            url = urljoin(self.instance_url, "/api/rest/2.0/ai/answer/create")
            csv_url = urljoin(self.instance_url, "/api/rest/2.0/report/answer")

            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key
            }
            query_payload = {
                "query": self.query,
                "metadata_identifier": self.model_id
            }

            async with httpx.AsyncClient() as client:
                # First POST to create the answer
                response = await client.post(url, json=query_payload, headers=headers)
                response_data = response.json()

                # Prepare the session payload for the CSV request
                session_payload = {
                    "file_format": "CSV",
                    "session_identifier": response_data["session_identifier"],
                    "generation_number": response_data["generation_number"]
                }

                # Second POST to retrieve the CSV
                csv_response = await client.post(csv_url, json=session_payload, headers=headers)

            return Data(data={"result": csv_response.text})
        except AttributeError as e:
            return Data(data={"result": f"Error processing inputs: {e!s}"})
        except httpx.HTTPError as e:
            return Data(data={"result": f"HTTP error occurred: {e!s}"})
