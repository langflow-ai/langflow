---
title: Quickstart
slug: /get-started-quickstart
---

import Icon from "@site/src/components/icon";
import DownloadableJsonFile from "@theme/DownloadableJsonFile";

Get started quickly with Langflow by loading a template, modifying it, and running it.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Run the agent template flow

Langflow includes template flows to demonstrate different use cases.

1. To open the **Simple Agent** template flow, click **New Flow**, and then select **Simple Agent**.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

This flow connects [Chat I/O](/components-chat-io) components with an [Agent](/components-agent) component.
As you ask the agent questions, it may call the connected [Calculator](/components-helpers#calculator) and [URL](/components-data#url) tools to answer.

2. In the agent component, in the **OpenAI API Key** field, add your OpenAI API key.

3. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**.

4. Ask the agent a simple math question, such as `I want to add 4 and 4.`
The Playground displays the agent's reasoning process as it correctly selects the Calculator component's `evaluate_expression` action.

![Playground with Agent calculator tool](/img/quickstart-simple-agent-playground.png)

5. Ask the agent about current events.
For this request, the agent selects the URL component's `fetch_content` action, and returns a summary of current headlines.

You have successfully run your first flow.

## Call your flows from applications

Langflow is an IDE, but it's also a runtime you can call through an API with Python, JavaScript, or curl.

The **Chat Input** component in your flow is not only a way to chat within the IDE. It is also an interface to accept external calls from your applications.

In the **Playground**, click **Share**, and then click **API access**.

The API access pane presents code snippets to get you started calling Langflow from your applications.

Choose your language and follow along!

<details open>
<summary>Python</summary>

```python
import requests

url = "http://127.0.0.1:7861/api/v1/run/0373ff1f-0173-4314-b6b6-959e5f39987b"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": "hello world!"
}

# Request headers
headers = {
    "Content-Type": "application/json"
}

try:
    # Send API request
    response = requests.request("POST", url, json=payload, headers=headers)
    response.raise_for_status()  # Raise exception for bad status codes

    # Print response
    print(response.text)

except requests.exceptions.RequestException as e:
    print(f"Error making API request: {e}")
except ValueError as e:
    print(f"Error parsing response: {e}")
```

The `url` value at the `/api/v1/run/` endpoint is the endpoint your application passes the values in `payload` to.
The `payload` is the request data. Its schema is defined [here](), but it accepts these parameters.

```json
payload = {
    "input_value": "your question here",  # Required: The text you want to send
    "input_type": "chat",                 # Optional: Default is "chat"
    "output_type": "chat",                # Optional: Default is "chat"
    "output_component": "",               # Optional: Specify output component if needed
    "tweaks": None,                      # Optional: Custom adjustments
    "session_id": None                   # Optional: For conversation context
}
```

Executing the copied snippet returns a lot of JSON:

<details open>
<summary>Result</summary>

```json
{"session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","outputs":[{"inputs":{"input_value":"hello world!"},"outputs":[{"results":{"message":{"text_key":"text","data":{"timestamp":"2025-06-12 22:04:57 UTC","sender":"Machine","sender_name":"AI","session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","text":"Hello! 🌍 How can I help you today?","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"Agent-JusP5","display_name":"Agent","source":"gpt-4.1"},"icon":"bot","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[{"title":"Agent Steps","contents":[{"type":"text","duration":1,"header":{"title":"Input","icon":"MessageSquare"},"text":"**Input**: hello world!"},{"type":"text","duration":52,"header":{"title":"Output","icon":"MessageSquare"},"text":"Hello! 🌍 How can I help you today?"}],"allow_markdown":true,"media_url":null}],"id":"83e1b8c9-eb51-403a-8d3e-17e597710125","flow_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","duration":null},"default_value":"","text":"Hello! 🌍 How can I help you today?","sender":"Machine","sender_name":"AI","files":[],"session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","timestamp":"2025-06-12T22:04:57+00:00","flow_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"Agent-JusP5","display_name":"Agent","source":"gpt-4.1"},"icon":"bot","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[{"title":"Agent Steps","contents":[{"type":"text","duration":1,"header":{"title":"Input","icon":"MessageSquare"},"text":"**Input**: hello world!"},{"type":"text","duration":52,"header":{"title":"Output","icon":"MessageSquare"},"text":"Hello! 🌍 How can I help you today?"}],"allow_markdown":true,"media_url":null}],"duration":null}},"artifacts":{"message":"Hello! 🌍 How can I help you today?","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"outputs":{"message":{"message":"Hello! 🌍 How can I help you today?","type":"text"}},"logs":{"message":[]},"messages":[{"message":"Hello! 🌍 How can I help you today?","sender":"Machine","sender_name":"AI","session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","stream_url":null,"component_id":"ChatOutput-SZSXV","files":[],"type":"text"}],"timedelta":null,"duration":null,"component_display_name":"Chat Output","component_id":"ChatOutput-SZSXV","used_frozen_result":false}]}]}
```

</details>


This confirms the call succeeded, but let's do something more with the returned value.

This example creates a question-and-answer chat.

```python
import requests
import json

url = "http://127.0.0.1:7861/api/v1/run/0373ff1f-0173-4314-b6b6-959e5f39987b"

def ask_agent(question):
    payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": question
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        # Get the response message
        data = response.json()
        message = data["outputs"][0]["outputs"][0]["outputs"]["message"]["message"]
        return message

    except Exception as e:
        return f"Error: {str(e)}"

# Get user input
print("Ask the agent anything (e.g., 'What is 15 * 7?' or 'What is the square root of 144?')")
user_question = input("Your question: ")

# Get and display the answer
result = ask_agent(user_question)
print(f"\nAgent's answer: {result}")
```




