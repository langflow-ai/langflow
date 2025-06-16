---
title: Quickstart
slug: /get-started-quickstart
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Get started with Langflow by loading a flow, running it, and then serving your flow at the `/run` API endpoint.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Run the agent template flow

Load the **Simple Agent** template flow, add your OpenAI API key to the agent, and run the flow.

1. To open the **Simple Agent** template flow, click **New Flow**, and then select **Simple Agent**.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

This flow connects [Chat I/O](/components-io) components with an [Agent](/components-agents) component.
As you ask the agent questions, it calls the connected [Calculator](/components-helpers#calculator) and [URL](/components-data#url) tools for answers, depending on the question.
2. In the agent component, in the **OpenAI API Key** field, add your OpenAI API key.

3. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**.

4. Ask the agent a simple math question, such as `I want to add 4 and 4.`
The Playground displays the agent's reasoning process as it correctly selects the Calculator component's `evaluate_expression` action.

![Playground with Agent calculator tool](/img/quickstart-simple-agent-playground.png)

5. Ask the agent about current events.
For this request, the agent selects the URL component's `fetch_content` action, and returns a summary of current headlines.

You have successfully run your first flow.

Optionally, stop here if you just want to create more flows within Langflow.

If you want to learn how Langflow integrates into external applications, read on.

## Run your flows from external applications

Langflow is an IDE, but it's also a runtime you can call through an API with Python, JavaScript, or curl.
If your server is running, you can POST a request to the `/run` endpoint to run the flow and get the result.

The **API access** pane includes code snippets to get you started sending requests to the server.

1. To open the **API access pane**, in the **Playground**, click **Share**, and then click **API access**.

<Tabs groupId="Language">
  <TabItem value="Python" label="Python" default>

```python
import requests

url = "http://127.0.0.1:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6"  # The complete API endpoint URL for this flow

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

  </TabItem>
  <TabItem value="JavaScript" label="JavaScript">

```js
const payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": "hello world!",
    "session_id": "user_1"
};

const options = {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
};

fetch('http://localhost:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6', options)
    .then(response => response.json())
    .then(response => console.log(response))
    .catch(err => console.error(err));
```

  </TabItem>

  <TabItem value="curl" label="curl">

```text
curl --request POST \
     --url 'http://localhost:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6?stream=false' \
     --header 'Content-Type: application/json' \
     --data '{
		           "output_type": "chat",
		           "input_type": "chat",
		           "input_value": "hello world!"
		         }'

# A 200 response confirms the call succeeded.
```

  </TabItem>

</Tabs>

The default code in the API access pane constructs a request with the Langflow server `url`, `headers`, and a `payload` of request data.

The payload schema is defined in [schemas.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/api/v1/schemas.py#L354). and accepts the following parameters.

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

2. Copy the snippet to your terminal, and send the request.

<details closed>
<summary>Response</summary>

```json
{
  "session_id": "29deb764-af3f-4d7d-94a0-47491ed241d6",
  "outputs": [
    {
      "inputs": {
        "input_value": "hello world!"
      },
      "outputs": [
        {
          "results": {
            "message": {
              "text_key": "text",
              "data": {
                "timestamp": "2025-06-16 19:58:23 UTC",
                "sender": "Machine",
                "sender_name": "AI",
                "session_id": "29deb764-af3f-4d7d-94a0-47491ed241d6",
                "text": "Hello world! 🌍 How can I assist you today?",
                "files": [],
                "error": false,
                "edit": false,
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": false,
                  "source": {
                    "id": "Agent-ZOknz",
                    "display_name": "Agent",
                    "source": "gpt-4o-mini"
                  },
                  "icon": "bot",
                  "allow_markdown": false,
                  "positive_feedback": null,
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [
                  {
                    "title": "Agent Steps",
                    "contents": [
                      {
                        "type": "text",
                        "duration": 2,
                        "header": {
                          "title": "Input",
                          "icon": "MessageSquare"
                        },
                        "text": "**Input**: hello world!"
                      },
                      {
                        "type": "text",
                        "duration": 226,
                        "header": {
                          "title": "Output",
                          "icon": "MessageSquare"
                        },
                        "text": "Hello world! 🌍 How can I assist you today?"
                      }
                    ],
                    "allow_markdown": true,
                    "media_url": null
                  }
                ],
                "id": "f3d85d9a-261c-4325-b004-95a1bf5de7ca",
                "flow_id": "29deb764-af3f-4d7d-94a0-47491ed241d6",
                "duration": null
              },
              "default_value": "",
              "text": "Hello world! 🌍 How can I assist you today?",
              "sender": "Machine",
              "sender_name": "AI",
              "files": [],
              "session_id": "29deb764-af3f-4d7d-94a0-47491ed241d6",
              "timestamp": "2025-06-16T19:58:23+00:00",
              "flow_id": "29deb764-af3f-4d7d-94a0-47491ed241d6",
              "error": false,
              "edit": false,
              "properties": {
                "text_color": "",
                "background_color": "",
                "edited": false,
                "source": {
                  "id": "Agent-ZOknz",
                  "display_name": "Agent",
                  "source": "gpt-4o-mini"
                },
                "icon": "bot",
                "allow_markdown": false,
                "positive_feedback": null,
                "state": "complete",
                "targets": []
              },
              "category": "message",
              "content_blocks": [
                {
                  "title": "Agent Steps",
                  "contents": [
                    {
                      "type": "text",
                      "duration": 2,
                      "header": {
                        "title": "Input",
                        "icon": "MessageSquare"
                      },
                      "text": "**Input**: hello world!"
                    },
                    {
                      "type": "text",
                      "duration": 226,
                      "header": {
                        "title": "Output",
                        "icon": "MessageSquare"
                      },
                      "text": "Hello world! 🌍 How can I assist you today?"
                    }
                  ],
                  "allow_markdown": true,
                  "media_url": null
                }
              ],
              "duration": null
            }
          },
          "artifacts": {
            "message": "Hello world! 🌍 How can I assist you today?",
            "sender": "Machine",
            "sender_name": "AI",
            "files": [],
            "type": "object"
          },
          "outputs": {
            "message": {
              "message": "Hello world! 🌍 How can I assist you today?",
              "type": "text"
            }
          },
          "logs": {
            "message": []
          },
          "messages": [
            {
              "message": "Hello world! 🌍 How can I assist you today?",
              "sender": "Machine",
              "sender_name": "AI",
              "session_id": "29deb764-af3f-4d7d-94a0-47491ed241d6",
              "stream_url": null,
              "component_id": "ChatOutput-aF5lw",
              "files": [],
              "type": "text"
            }
          ],
          "timedelta": null,
          "duration": null,
          "component_display_name": "Chat Output",
          "component_id": "ChatOutput-aF5lw",
          "used_frozen_result": false
        }
      ]
    }
  ]
}
```

</details>

This response confirms the call succeeded, but let's do something more with the returned answer from the agent.

The following example builds on the API pane's example code to create a question-and-answer chat in your terminal that stores the Agent's previous answer.

3. Copy the code into your terminal, and run it.
4. To view the Agent's previous answer, type `compare`. To close the terminal chat, type `