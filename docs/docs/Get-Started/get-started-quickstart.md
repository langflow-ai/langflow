---
title: Quickstart
slug: /get-started-quickstart
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';
import getStartedJavascript from '!!raw-loader!./examples/get-started.js';
import getStartedPython from '!!raw-loader!./examples/get-started.py';
import playgroundJavascriptCode from '!!raw-loader!./examples/playground-default.js';
import playgroundPythonCode from '!!raw-loader!./examples/playground-default.py';
import playgroundCurlCode from '!!raw-loader!./examples/playground-default.sh';

Get started quickly with Langflow by loading a flow and running it.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Run the agent template flow

Langflow includes template flows to demonstrate use cases.

1. To open the **Simple Agent** template flow, click **New Flow**, and then select **Simple Agent**.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

This flow connects [Chat I/O](/components-chat-io) components with an [Agent](/components-agent) component.
As you ask the agent questions, it calls the connected [Calculator](/components-helpers#calculator) and [URL](/components-data#url) tools for answers, depending on the question.

2. In the agent component, in the **OpenAI API Key** field, add your OpenAI API key.

3. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**.

4. Ask the agent a simple math question, such as `I want to add 4 and 4.`
The Playground displays the agent's reasoning process as it correctly selects the Calculator component's `evaluate_expression` action.

![Playground with Agent calculator tool](/img/quickstart-simple-agent-playground.png)

5. Ask the agent about current events.
For this request, the agent selects the URL component's `fetch_content` action, and returns a summary of current headlines.

You have successfully run your first flow.
You can stop here if you just want to create more flows within Langflow.
If you want to learn how Langflow integrates into external applications, read on.

## Run your flows from external applications

Langflow is an IDE, but it's also a runtime you can call through an API with Python, JavaScript, or curl.
If your server is running, you can POST a request to the `/run` endpoint to run the flow.

The **API access** pane includes code snippets to get you started sending requests to the server.

The default code in the API access pane constructs a request with the Langflow server URL, headers, and a `payload` of request data.

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

1. To open the **API access pane**, in the **Playground**, click **Share**, and then click **API access**.

<Tabs groupId="Language">
  <TabItem value="Python" label="Python" default>

    <CodeBlock language="py" title="examples/playground-default.py">{playgroundPythonCode}</CodeBlock>

  </TabItem>
  <TabItem value="JavaScript" label="JavaScript">

    <CodeBlock language="js" title="examples/playground-default.js">{playgroundJavascriptCode}</CodeBlock>

  </TabItem>

  <TabItem value="curl" label="curl">

    <CodeBlock language="curl" title="examples/playground-default.sh">{playgroundCurlCode}</CodeBlock>

  </TabItem>

</Tabs>

2. Copy the snippet to your terminal, and send the request.
<details open>
<summary>Result</summary>

```json
{"session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","outputs":[{"inputs":{"input_value":"hello world!"},"outputs":[{"results":{"message":{"text_key":"text","data":{"timestamp":"2025-06-12 22:04:57 UTC","sender":"Machine","sender_name":"AI","session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","text":"Hello! 🌍 How can I help you today?","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"Agent-JusP5","display_name":"Agent","source":"gpt-4.1"},"icon":"bot","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[{"title":"Agent Steps","contents":[{"type":"text","duration":1,"header":{"title":"Input","icon":"MessageSquare"},"text":"**Input**: hello world!"},{"type":"text","duration":52,"header":{"title":"Output","icon":"MessageSquare"},"text":"Hello! 🌍 How can I help you today?"}],"allow_markdown":true,"media_url":null}],"id":"83e1b8c9-eb51-403a-8d3e-17e597710125","flow_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","duration":null},"default_value":"","text":"Hello! 🌍 How can I help you today?","sender":"Machine","sender_name":"AI","files":[],"session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","timestamp":"2025-06-12T22:04:57+00:00","flow_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"Agent-JusP5","display_name":"Agent","source":"gpt-4.1"},"icon":"bot","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[{"title":"Agent Steps","contents":[{"type":"text","duration":1,"header":{"title":"Input","icon":"MessageSquare"},"text":"**Input**: hello world!"},{"type":"text","duration":52,"header":{"title":"Output","icon":"MessageSquare"},"text":"Hello! 🌍 How can I help you today?"}],"allow_markdown":true,"media_url":null}],"duration":null}},"artifacts":{"message":"Hello! 🌍 How can I help you today?","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"outputs":{"message":{"message":"Hello! 🌍 How can I help you today?","type":"text"}},"logs":{"message":[]},"messages":[{"message":"Hello! 🌍 How can I help you today?","sender":"Machine","sender_name":"AI","session_id":"0373ff1f-0173-4314-b6b6-959e5f39987b","stream_url":null,"component_id":"ChatOutput-SZSXV","files":[],"type":"text"}],"timedelta":null,"duration":null,"component_display_name":"Chat Output","component_id":"ChatOutput-SZSXV","used_frozen_result":false}]}]}
```

</details>


This response confirms the call succeeded, but let's do something more with the returned answer from the agent.

This example creates a question-and-answer chat in your terminal, and stores the previous answer. To view the previous answer, type `compare`.

<Tabs groupId="Languages">
  <TabItem value="Python" label="Python" default>

    <CodeBlock language="Python" title="examples/get-started.py">{getStartedPython}</CodeBlock>

  </TabItem>
  <TabItem value="JavaScript" label="JavaScript">

    <CodeBlock language="JavaScript" title="examples/playground-default.js">{playgroundJavascriptCode}</CodeBlock>

  </TabItem>
</Tabs>




This response confirms the call succeeded, but let's do something more with the returned answer from the agent.

This example creates a question-and-answer chat in your terminal, and stores the previous answer. To view the previous answer, type `compare`.

## Apply temporary overrides to a flow run

To change a flow's values at runtime, Langflow offers **Temporary Overrides**, also called **Tweaks**.
Tweaks are added to the API request to the `/run` endpoint, and temporarily change component parameters within your flow.
They don't modify the underlying flow configuration or persist between runs.

The easiest way to modify your request with tweaks to the `/run` endpoint is in the **API access** pane, in the **Input schema** pane.

1. In the **Input schema** pane, select the parameter you want to modify in your next request.
Enabling parameters in the **Input schema** pane does not **allow** modifications to the listed parameters. It only adds them to the example code.
2. For example, to change the LLM provider from OpenAI to Groq, and include your Groq API key with the request, select the values **Model Providers**, **Model**, and **Groq API Key**.
The parameters are added to the sample code in the API pane's request.
Inspect your request's payload with the added tweaks.

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

3. Copy the code snippet from the **API access** pane into your terminal.
Replace `GROQ_API_KEY` with your Groq API key, and run your application.
You have run your flow without modifying the components themselves, but only passing tweaks with the request.





