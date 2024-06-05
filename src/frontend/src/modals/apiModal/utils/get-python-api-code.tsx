/**
 * Function to get the python code for the API
 * @param {string} flowId - The id of the flow
 * @param {boolean} isAuth - If the API is authenticated
 * @param {any[]} tweak - The tweaks
 * @returns {string} - The python code
 */
export default function getPythonApiCode(
  flowId: string,
  isAuth: boolean,
  tweaksBuildedObject,
): string {
  const tweaksObject = tweaksBuildedObject[0];
  return `import requests
from typing import Optional

BASE_API_URL = "${window.location.protocol}//${window.location.host}/api/v1/run"
FLOW_ID = "${flowId}"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = ${JSON.stringify(tweaksObject, null, 2)}

def run_flow(message: str,
  flow_id: str,
  output_type: str = "chat",
  input_type: str = "chat",
  tweaks: Optional[dict] = None,
  api_key: Optional[str] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {
        "input_value": message,
        "output_type": output_type,
        "input_type": input_type,
    }
    headers = None
    if tweaks:
        payload["tweaks"] = tweaks
    if api_key:
        headers = {"x-api-key": api_key}
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

# Setup any tweaks you want to apply to the flow
message = "message"
${!isAuth ? `api_key = "<your api key>"` : ""}
print(run_flow(message=message, flow_id=FLOW_ID, tweaks=TWEAKS${
    !isAuth ? `, api_key=api_key` : ""
  }))`;
}
