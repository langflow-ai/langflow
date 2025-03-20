---
title: API keys
slug: /configuration-api-keys
---

Langflow provides an API key functionality that allows users to access their individual components and flows without traditional login authentication. The API key is a user-specific token that can be included in the request header, query parameter, or as a command line argument to authenticate API calls. This documentation outlines how to generate, use, and manage API keys in Langflow.

:::info

The default user and password are set using the LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD environment variables. The default values are `langflow` and `langflow`, respectively.

:::

## Generate an API key

Generate a user-specific token to use with Langflow.

### Generate an API key with the Langflow UI

1. Click your user icon and select **Settings**.
2. Click **Langflow API**, and then click **Add New**.
3. Name your key, and then click **Create Secret Key**.
4. Copy the API key and store it in a secure location.

### Generate an API key with the Langflow CLI

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

## Authenticate requests with the Langflow API key

Include your API key in API requests to authenticate requests to Langflow.

### Include the API key in the HTTP header

To use the API key when making API requests with cURL, include the API key in the HTTP header.

```shell
curl -X POST \
  "http://127.0.0.1:7860/api/v1/run/*`YOUR_FLOW_ID`*?stream=false" \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: *`YOUR_API_KEY`*' \
  -d '{"inputs": {"text":""}, "tweaks": {}}'
```

To instead pass the API key as a query parameter, do the following:

```shell
curl -X POST \
  "http://127.0.0.1:7860/api/v1/run/*`YOUR_FLOW_ID`*?x-api-key=*`YOUR_API_KEY`*?stream=false" \
  -H 'Content-Type: application/json' \
  -d '{"inputs": {"text":""}, "tweaks": {}}'
```

To use the API key when making API requests with the Python `requests` library, include the API key as a variable string.

```python
import argparse
import json
from argparse import RawTextHelpFormatter
import requests
from typing import Optional
import warnings
try:
    from langflow.load import upload_file
except ImportError:
    warnings.warn("Langflow provides a function to help you upload files to the flow. Please install langflow to use it.")
    upload_file = None

BASE_API_URL = "http://127.0.0.1:7860"
FLOW_ID = "*`YOUR_FLOW_ID`*"
ENDPOINT = "" # You can set a specific endpoint name in the flow settings

# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = {
  "ChatInput-8a86T": {},
  "Prompt-pKfl9": {},
  "ChatOutput-WcGpD": {},
  "OpenAIModel-5UyvQ": {}
}

def run_flow(message: str,
  endpoint: str,
  output_type: str = "chat",
  input_type: str = "chat",
  tweaks: Optional[dict] = None,
  api_key: Optional[str] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param endpoint: The ID or the endpoint name of the flow
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/api/v1/run/{endpoint}"

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

def main():
    parser = argparse.ArgumentParser(description="""Run a flow with a given message and optional tweaks.
Run it like: python <your file>.py "your message here" --endpoint "your_endpoint" --tweaks '{"key": "value"}'""",
        formatter_class=RawTextHelpFormatter)
    parser.add_argument("message", type=str, help="The message to send to the flow")
    parser.add_argument("--endpoint", type=str, default=ENDPOINT or FLOW_ID, help="The ID or the endpoint name of the flow")
    parser.add_argument("--tweaks", type=str, help="JSON string representing the tweaks to customize the flow", default=json.dumps(TWEAKS))
    parser.add_argument("--api_key", type=str, help="API key for authentication", default=None)
    parser.add_argument("--output_type", type=str, default="chat", help="The output type")
    parser.add_argument("--input_type", type=str, default="chat", help="The input type")
    parser.add_argument("--upload_file", type=str, help="Path to the file to upload", default=None)
    parser.add_argument("--components", type=str, help="Components to upload the file to", default=None)

    args = parser.parse_args()
    try:
      tweaks = json.loads(args.tweaks)
    except json.JSONDecodeError:
      raise ValueError("Invalid tweaks JSON string")

    if args.upload_file:
        if not upload_file:
            raise ImportError("Langflow is not installed. Please install it to use the upload_file function.")
        elif not args.components:
            raise ValueError("You need to provide the components to upload the file to.")
        tweaks = upload_file(file_path=args.upload_file, host=BASE_API_URL, flow_id=args.endpoint, components=[args.components], tweaks=tweaks)

    response = run_flow(
        message=args.message,
        endpoint=args.endpoint,
        output_type=args.output_type,
        input_type=args.input_type,
        tweaks=tweaks,
        api_key=args.api_key
    )

    print(json.dumps(response, indent=2))

if __name__ == "__main__":
    main()

```

To pass the API key to your script with a command line argument, do the following:

```shell
python your_script.py "*`YOUR_INPUT_MESSAGE`*" --api_key "*`YOUR_API_KEY`*"
```

## Security considerations

- **Visibility**: For security reasons, the API key cannot be retrieved again through the UI.
- **Scope**: The key allows access only to the flows and components of the specific user to whom it was issued.

## Custom API endpoint

To choose a custom name for your API endpoint, select **Project Settings** &gt; **Endpoint Name** and name your endpoint.

## Revoke an API key

To revoke an API key, delete it from the list of keys in the **Settings** menu.

1. Click your user icon and select **Settings**.
2. Click **Langflow API**.
3. Select the keys you want to delete and click the trash can icon.

This action immediately invalidates the key and prevents it from being used again.


## API Key Management

### Authentication API Keys

These keys allow programmatic access to Langflow's API. To create a Langflow API key:

1. Generate a key with the CLI:
```text
# Generate via CLI
langflow api-key
```

2. Include the API key as a header in requests to the Langflow API.
```text
curl -X POST \
  "http://127.0.0.1:7860/api/v1/flows/" \
  -H "x-api-key: your_api_key"
```

### Component API Keys

These are credentials for external services like OpenAI. They can be managed with the `.env` file or in the Langflow UI.

To add component API keys to your `.env` file:

```text
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GOOGLE_API_KEY=...
```

To add component API keys with the Langflow UI:

  1. Go to Settings > Global Variables
  2. Add new API keys as Credential type variables
  3. Apply them to specific component fields

## Secret Key Management

### LANGFLOW_SECRET_KEY

This environment variable holds a secret key used for encrypting sensitive data like API keys.

```bash
LANGFLOW_SECRET_KEY=dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fb
```

Langflow uses the [Fernet](https://pypi.org/project/cryptography/) library for secret key encryption.

### Create a LANGFLOW_SECRET_KEY

The `LANGFLOW_SECRET_KEY` is used for encrypting sensitive data. It must be:
- At least 32 bytes long
- URL-safe base64 encoded

1. To create a `LANGFLOW_SECRET_KEY`, run the following command:

<Tabs>
<TabItem value="unix" label="macOS/Linux">

```bash
# Copy to clipboard (macOS)
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | pbcopy

# Copy to clipboard (Linux)
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | xclip -selection clipboard

# Or just print
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')"
```
</TabItem>

<TabItem value="windows" label="Windows">

```bash
# Copy to clipboard
python -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | clip

# Or just print
python -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')"
```

</TabItem>
</Tabs>

The command generates a secure key like `dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fbg`.
Treat the generated secure key as you would an application access token. Do not commit the key to code and keep it in a safe place.

2. Create a `.env` file with the following configuration, and include your generated secret key value.
```bash
LANGFLOW_AUTO_LOGIN=False
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=securepassword
LANGFLOW_SECRET_KEY=dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fbg  # Your generated key
LANGFLOW_NEW_USER_IS_ACTIVE=False
```

3. Start Langflow with the values from your `.env`

