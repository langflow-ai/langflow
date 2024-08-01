---
title: API Keys
sidebar_position: 1
slug: /configuration-api-keys
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




Langflow provides an API key functionality that allows users to access their individual components and flows without traditional login authentication. The API key is a user-specific token that can be included in the request header or query parameter to authenticate API calls. This documentation outlines how to generate, use, and manage API keys in Langflow.


:::info

The default user and password are set using the LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD environment variables. The default values are langflow and langflow, respectively.

:::




## Generate an API key {#c29986a69cad4cdbbe7537e383ea7207}


Generate a user-specific token to use with Langflow.


### Generate an API key with the Langflow UI {#3d90098ddd7c44b6836c0273acf57123}

1. Click on the "API Key" icon.

	![](./596474918.png)

2. Click on "Create new secret key".
3. Give it an optional name.
4. Click on "Create secret key".
5. Copy the API key and store it in a secure location.

### Generate an API key with the Langflow CLI {#2368f62fc4b8477e8080c9c2d3659d76}


```shell
langflow api-key
# or
python -m langflow api-key
╭─────────────────────────────────────────────────────────────────────╮
│ API Key Created Successfully:                                       │
│                                                                     │
│ sk-O0elzoWID1izAH8RUKrnnvyyMwIzHi2Wk-uXWoNJ2Ro                      │
│                                                                     │
│ This is the only time the API key will be displayed.                │
│ Make sure to store it in a secure location.                         │
│                                                                     │
│ The API key has been copied to your clipboard. Cmd + V to paste it. │
╰──────────────────────────────

```


## Use the Langflow API key {#ae787e4b0d3846aa9094fac75e0ac04f}


Include your API key in API requests to authenticate requests to Langflow.


### Use the `x-api-key` header {#70965b3ad24d467ca4f90e7c13a1f394}


Include the `x-api-key` in the HTTP header when making API requests:


```shell
curl -X POST \\
  <http://localhost:3000/api/v1/run/><your_flow_id> \\
  -H 'Content-Type: application/json'\\
  -H 'x-api-key: <your api key>'\\
  -d '{"inputs": {"text":""}, "tweaks": {}}'

```


With Python using `requests`:


```python
import requests
from typing import Optional

BASE_API_URL = "<http://localhost:3001/api/v1/process>"
FLOW_ID = "4441b773-0724-434e-9cee-19d995d8f2df"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = {}

def run_flow(inputs: dict,
            flow_id: str,
            tweaks: Optional[dict] = None,
            apiKey: Optional[str] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {"inputs": inputs}
    headers = {}

    if tweaks:
        payload["tweaks"] = tweaks
    if apiKey:
        headers = {"x-api-key": apiKey}

    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

# Setup any tweaks you want to apply to the flow
inputs = {"text":""}
api_key = "<your api key>"
print(run_flow(inputs, flow_id=FLOW_ID, tweaks=TWEAKS, apiKey=api_key))

```


### Use the query parameter {#febb797f3bb5403b9f070afc0fa4f453}


Include the API key as a query parameter in the URL:


```shell
curl -X POST \\
  <http://localhost:3000/api/v1/process/><your_flow_id>?x-api-key=<your_api_key> \\
  -H 'Content-Type: application/json'\\
  -d '{"inputs": {"text":""}, "tweaks": {}}'

```


With Python using `requests`:


```python
import requests

BASE_API_URL = "<http://localhost:3001/api/v1/process>"
FLOW_ID = "4441b773-0724-434e-9cee-19d995d8f2df"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = {}

def run_flow(inputs: dict,
            flow_id: str,
            tweaks: Optional[dict] = None,
            apiKey: Optional[str] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {"inputs": inputs}
    headers = {}

    if tweaks:
        payload["tweaks"] = tweaks
    if apiKey:
        api_url += f"?x-api-key={apiKey}"

    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

# Setup any tweaks you want to apply to the flow
inputs = {"text":""}
api_key = "<your api key>"
print(run_flow(inputs, flow_id=FLOW_ID, tweaks=TWEAKS, apiKey=api_key))

```


## Security Considerations {#1273eb69a61344d19827b30dba46dfd5}

- **Visibility**: For security reasons, the API key cannot be retrieved again through the UI.
- **Scope**: The key allows access only to the flows and components of the specific user to whom it was issued.

## Custom API endpoint {#da933a86690a4fdeac24024472caf8a9}


Under **Project Settings** &gt; **Endpoint Name**, you can pick a custom name for the endpoint used to call your flow from the API.


## Revoke an API Key {#f0ea41ea167845cea91bb5e8f90d9df0}


To revoke an API key, delete it from the UI. This action immediately invalidates the key and prevents it from being used again.

