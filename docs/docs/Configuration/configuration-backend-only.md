---
title: Backend-Only
sidebar_position: 4
slug: /configuration-backend-only
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




You can run Langflow in `--backend-only` mode to expose your Langflow app as an API, without running the frontend UI.


Start langflow in backend-only mode with `python3 -m langflow run --backend-only`.


The terminal prints `Welcome to ⛓ Langflow`, and a blank window opens at `http://127.0.0.1:7864/all`.
Langflow will now serve requests to its API without the frontend running.


## Prerequisites {#81dfa9407ed648889081b9d08b0e5cfe}

- [Langflow installed](/getting-started-installation)
- [OpenAI API key](https://platform.openai.com/)
- [A Langflow flow created](/starter-projects-basic-prompting)

## Download your flow's curl call {#d2cf1b694e4741eca07fd9806516007b}

1. Click API.
2. Click **curl** &gt; **Copy code** and save the code to your local machine.
It will look something like this:

```text
curl -X POST \\
    "<http://127.0.0.1:7864/api/v1/run/ef7e0554-69e5-4e3e-ab29-ee83bcd8d9ef?stream=false>" \\
    -H 'Content-Type: application/json'\\
    -d '{"input_value": "message",
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": {
  "Prompt-kvo86": {},
  "OpenAIModel-MilkD": {},
  "ChatOutput-ktwdw": {},
  "ChatInput-xXC4F": {}
}}'

```


Note the flow ID of `ef7e0554-69e5-4e3e-ab29-ee83bcd8d9ef`. You can find this ID in the UI as well to ensure you're querying the right flow.


## Start Langflow in backend-only mode {#f0ba018daf3041c39c0d226dadf78d35}

1. Stop Langflow with Ctrl+C.
2. Start langflow in backend-only mode with `python3 -m langflow run --backend-only`.
The terminal prints `Welcome to ⛓ Langflow`, and a blank window opens at `http://127.0.0.1:7864/all`.
Langflow will now serve requests to its API.
3. Run the curl code you copied from the UI.
You should get a result like this:

```shell
{"session_id":"ef7e0554-69e5-4e3e-ab29-ee83bcd8d9ef:bf81d898868ac87e1b4edbd96c131c5dee801ea2971122cc91352d144a45b880","outputs":[{"inputs":{"input_value":"hi, are you there?"},"outputs":[{"results":{"result":"Arrr, ahoy matey! Aye, I be here. What be ye needin', me hearty?"},"artifacts":{"message":"Arrr, ahoy matey! Aye, I be here. What be ye needin', me hearty?","sender":"Machine","sender_name":"AI"},"messages":[{"message":"Arrr, ahoy matey! Aye, I be here. What be ye needin', me hearty?","sender":"Machine","sender_name":"AI","component_id":"ChatOutput-ktwdw"}],"component_display_name":"Chat Output","component_id":"ChatOutput-ktwdw","used_frozen_result":false}]}]}%

```


Again, note that the flow ID matches.
Langflow is receiving your POST request, running the flow, and returning the result, all without running the frontend. Cool!


## Download your flow's Python API call {#5923ff9dc40843c7a22a72fa6c66540c}


Instead of using curl, you can download your flow as a Python API call instead.

1. Click API.
2. Click **Python API** &gt; **Copy code** and save the code to your local machine.
The code will look something like this:

```python
import requests
from typing import Optional

BASE_API_URL = "<http://127.0.0.1:7864/api/v1/run>"
FLOW_ID = "ef7e0554-69e5-4e3e-ab29-ee83bcd8d9ef"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}

def run_flow(message: str,
  flow_id: str,
  output_type: str = "chat",
  input_type: str = "chat",
  tweaks: Optional[dict] = None,
  api_key: Optional[str] = None) -> dict:
    """Run a flow with a given message and optional tweaks.

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
	
	print(run_flow(message=message, flow_id=FLOW_ID))

```


3. Run your Python app:


```shell
python3 app.py
```


The result is similar to the curl call:


```json
{'session_id': 'ef7e0554-69e5-4e3e-ab29-ee83bcd8d9ef:bf81d898868ac87e1b4edbd96c131c5dee801ea2971122cc91352d144a45b880', 'outputs': [{'inputs': {'input_value': 'message'}, 'outputs': [{'results': {'result': "Arrr matey! What be yer message for this ol' pirate? Speak up or walk the plank!"}, 'artifacts': {'message': "Arrr matey! What be yer message for this ol' pirate? Speak up or walk the plank!", 'sender': 'Machine', 'sender_name': 'AI'}, 'messages': [{'message': "Arrr matey! What be yer message for this ol' pirate? Speak up or walk the plank!", 'sender': 'Machine', 'sender_name': 'AI', 'component_id': 'ChatOutput-ktwdw'}], 'component_display_name': 'Chat Output', 'component_id': 'ChatOutput-ktwdw', 'used_frozen_result': False}]}]}

```


Your Python app POSTs to your Langflow server, and the server runs the flow and returns the result.


See [API](https://www.notion.so/administration/api) for more ways to interact with your headless Langflow server.

