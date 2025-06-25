---
title: Quickstart
slug: /get-started-quickstart
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Get started with Langflow by loading a template flow, running it, and then serving it at the `/run` API endpoint.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/api-keys)
- [A Langflow API key](/configuration-api-keys)

<details>
<summary>Need help creating an API key?</summary>

To generate a user-specific token to use with Langflow, do the following.

1. Open the Langflow UI, click your user icon, and then select **Settings**.
2. Click **Langflow API Keys**, and then click **Add New**.
3. Name your key, and then click **Create API Key**.
4. Copy the API key and store it in a secure location.
5. Include your `LANGFLOW_API_KEY` in requests like this:
    ```
    curl --request POST \
     --url 'http://localhost:7860/api/v1/run/0901b40b-9212-41cb-87c6-ac66a427913c?stream=false' \
     --header 'Content-Type: application/json' \
     --header 'x-api-key: LANGFLOW_API_KEY' \
     --data '{
       "output_type": "chat",
       "input_type": "chat",
       "input_value": "Hello"
     }'
    ```
</details>

## Run the Simple Agent template flow

1. In Langflow, click **New Flow**, and then select the **Simple Agent** template.

![Simple agent starter flow](/img/quickstart-simple-agent-flow.png)

The Simple Agent flow consists of an [Agent component](/agents) connected to [Chat I/O components](/components-io), a [Calculator component](/components-tools#calculator-tool), and a [URL component](/components-data#url). When you run this flow, you submit a query to the agent through the Chat Input component, the agent uses the Calculator and URL tools to generate a response, and then returns the response through the Chat Output component.

Many components can be tools for agents, including [Model Context Protocol (MCP) servers](/mcp-server). The agent decides which tools to call based on the context of a given query.

2. In the **Agent** component's settings, in the **OpenAI API Key** field, enter your OpenAI API key.
This guide uses an OpenAI model for demonstration purposes. If you want to use a different provider, change the **Model Provider** field, and then provide credentials for your selected provider.

    Optionally, you can click <Icon name="Globe" aria-hidden="true"/> **Globe** to store the key in a Langflow [global variable](/configuration-global-variables).

3. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**.

4. To test the Calculator tool, ask the agent a simple math question, such as `I want to add 4 and 4.`
To help you test and evaluate your flows, the Playground shows the agent's reasoning process as it analyzes the prompt, selects a tool, and then uses the tool to generate a response.
In this case, a math question causes the agent to select the Calculator tool and use an action like `evaluate_expression`.

![Playground with Agent tool](/img/quickstart-simple-agent-playground.png)

5. To test the URL tool, ask the agent about current events.
For this request, the agent selects the URL tool's `fetch_content` action, and then returns a summary of current news headlines.

6. When you are done testing the flow, click <Icon name="X" aria-hidden="true"/>**Close**.

Now that you've run your first flow, try these next steps:

- Edit your **Simple Agent** flow by attaching different tools or adding more components to the flow.
- Build your own flows from scratch or by modifying other template flows.
- Integrate flows into your applications, as explained in [Run your flows from external applications](#run-your-flows-from-external-applications).

Optionally, stop here if you just want to create more flows within Langflow.

If you want to learn how Langflow integrates into external applications, read on.

## Run your flows from external applications

Langflow is an IDE, but it's also a runtime you can call through an API with Python, JavaScript, or HTTP.

When you start Langflow locally, you can send requests to the local Langflow server.
For production applications, you need to deploy a stable Langflow instance to handle API calls.
For more information, see [Langflow deployment overview](/deployment-overview).

For example, you can use `POST /run` to run a flow and get the result.

Langflow provides code snippets to help you get started with the Langflow API.

1. To open the **API access pane**, in the **Playground**, click **Share**, and then click **API access**.

    The default code in the API access pane constructs a request with the Langflow server `url`, `headers`, and a `payload` of request data.
    The code snippets automatically include the `LANGFLOW_SERVER_ADDRESS` and `FLOW_ID` values for the flow.
    Replace these values if you're using the code for a different server or flow.
    The default Langflow server address is `http://localhost:7860`

    <Tabs groupId="Language">
      <TabItem value="Python" label="Python" default>

    ```python
    import requests

    url = "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID"  # The complete API endpoint URL for this flow

    # Request payload configuration
    payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": "hello world!"
    }

    # Request headers
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "LANGFLOW_API_KEY"
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
            'Content-Type': 'application/json',
            'x-api-key': 'LANGFLOW_API_KEY'
        },
        body: JSON.stringify(payload)
    };

    fetch('http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID', options)
        .then(response => response.json())
        .then(response => console.log(response))
        .catch(err => console.error(err));
    ```

      </TabItem>

      <TabItem value="curl" label="curl">

    ```text
    curl --request POST \
     --url 'http://localhost:7860/api/v1/run/0901b40b-9212-41cb-87c6-ac66a427913c?stream=false' \
     --header 'Content-Type: application/json' \
     --header 'x-api-key: LANGFLOW_API_KEY' \
     --data '{
       "output_type": "chat",
       "input_type": "chat",
       "input_value": "Hello"
     }'

    # A 200 response confirms the call succeeded.
    ```

      </TabItem>

    </Tabs>

2. Copy the snippet, paste it in a script file, and then run the script to send the request.
If you are using the curl snippet, you can run the command directly in your terminal.

If the request is successful, the response includes many details about the flow run, including the session ID, inputs, outputs, components, durations, and more.
The following is an example of a response from running the **Simple Agent** template flow:

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

In a production application, you probably want to select parts of this response to return to the user, store in logs, and so on. The next steps demonstrate how you can extract data from a Langflow API response to use in your application.

### Extract data from the response

The following example builds on the API pane's example code to create a question-and-answer chat in your terminal that stores the Agent's previous answer.

1. Incorporate your **Simple Agent** flow's `/run` snippet into the following script.
This script runs a question-and-answer chat in your terminal and stores the Agent's previous answer so you can compare them.


    <Tabs groupId="Languages">
      <TabItem value="Python" label="Python" default>

    ```python
    import requests
    import json

    url = "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID"

    def ask_agent(question):
        payload = {
            "output_type": "chat",
            "input_type": "chat",
            "input_value": question,
        }

        headers = {
        "Content-Type": "application/json",
        "x-api-key": "LANGFLOW_API_KEY"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            # Get the response message
            data = response.json()
            message = data["outputs"][0]["outputs"][0]["outputs"]["message"]["message"]
            return message

        except Exception as e:
            return f"Error: {str(e)}"

    def extract_message(data):
        try:
            return data["outputs"][0]["outputs"][0]["outputs"]["message"]["message"]
        except (KeyError, IndexError):
            return None

    # Store the previous answer from ask_agent response
    previous_answer = None

    # the terminal chat
    while True:
        # Get user input
        print("\nAsk the agent anything, such as 'What is 15 * 7?' or 'What is the capital of France?')")
        print("Type 'quit' to exit or 'compare' to see the previous answer")
        user_question = input("Your question: ")

        if user_question.lower() == 'quit':
            break
        elif user_question.lower() == 'compare':
            if previous_answer:
                print(f"\nPrevious answer was: {previous_answer}")
            else:
                print("\nNo previous answer to compare with!")
            continue

        # Get and display the answer
        result = ask_agent(user_question)
        print(f"\nAgent's answer: {result}")
        # Store the answer for comparison
        previous_answer = result
    ```

      </TabItem>
      <TabItem value="JavaScript" label="JavaScript">

    ```js
    const readline = require('readline');

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    const url = 'http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID';

    // Store the previous answer from askAgent response
    let previousAnswer = null;

    // the agent flow, with question as input_value
    async function askAgent(question) {
        const payload = {
            "output_type": "chat",
            "input_type": "chat",
            "input_value": question
        };

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': 'LANGFLOW_API_KEY'
            },
            body: JSON.stringify(payload)
        };

        try {
            const response = await fetch(url, options);
            const data = await response.json();

            // Extract the message from the nested response
            const message = data.outputs[0].outputs[0].outputs.message.message;
            return message;
        } catch (error) {
            return `Error: ${error.message}`;
        }
    }

    // the terminal chat
    async function startChat() {
        console.log("\nAsk the agent anything, such as 'What is 15 * 7?' or 'What is the capital of France?'");
        console.log("Type 'quit' to exit or 'compare' to see the previous answer");

        const askQuestion = () => {
            rl.question('\nYour question: ', async (userQuestion) => {
                if (userQuestion.toLowerCase() === 'quit') {
                    rl.close();
                    return;
                }

                if (userQuestion.toLowerCase() === 'compare') {
                    if (previousAnswer) {
                        console.log(`\nPrevious answer was: ${previousAnswer}`);
                    } else {
                        console.log("\nNo previous answer to compare with!");
                    }
                    askQuestion();
                    return;
                }

                const result = await askAgent(userQuestion);
                console.log(`\nAgent's answer: ${result}`);
                previousAnswer = result;
                askQuestion();
            });
        };

        askQuestion();
    }

    startChat();
    ```

      </TabItem>
    </Tabs>

2. To view the Agent's previous answer, type `compare`. To close the terminal chat, type `exit`.

### Use tweaks to apply temporary overrides to a flow run

You can include tweaks with your requests to temporarily modify flow parameters.
Tweaks are added to the API request, and temporarily change component parameters within your flow.
Tweaks override the flow's components' settings for a single run only.
They don't modify the underlying flow configuration or persist between runs.

Tweaks are added to the `/run` endpoint's `payload`.
To assist with formatting, you can define tweaks in Langflow's **Input Schema** pane before copying the code snippet.

1. To open the **Input Schema** pane, from the **API access** pane, click **Input Schema**.
2. In the **Input Schema** pane, select the parameter you want to modify in your next request.
Enabling parameters in the **Input Schema** pane does not **allow** modifications to the listed parameters. It only adds them to the example code.
3. For example, to change the LLM provider from OpenAI to Groq, and include your Groq API key with the request, select the values **Model Providers**, **Model**, and **Groq API Key**.
Langflow updates the `tweaks` object in the code snippets based on your input parameters, and includes default values to guide you.
Use the updated code snippets in your script to run your flow with your overrides.

```json
payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": "hello world!",
    "tweaks": {
        "Agent-ZOknz": {
            "agent_llm": "Groq",
            "api_key": "GROQ_API_KEY",
            "model_name": "llama-3.1-8b-instant"
        }
    }
}
```

## Next steps

* [Model Context Protocol (MCP) servers](/mcp-server)
* [Langflow deployment overview](/deployment-overview)