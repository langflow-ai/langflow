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

## Call your flows from applications

Langflow is an IDE, but it's also a runtime you can call through an API with Python, JavaScript, or curl.

The **Chat Input** component in your flow is not only a way to chat within the IDE. It is also an interface to accept external calls from your applications.

In the **Playground**, click **Share**, and then click **API access**.

The API access pane presents code snippets to call Langflow from your applications, with the URL, payload, and headers pre-filled in.

Choose your language and follow along.

<Tabs groupId="Language">
<TabItem value="Python" label="Python">

The default code in the API access pane

<details open>
<summary>Python</summary>

<CodeBlock language="Python" title="examples/playground-default.py">{playgroundPythonCode}</CodeBlock>

</details>

The `url` value at the `/api/v1/run/` endpoint is the endpoint your application passes the values in `payload` to.
The `payload` is the request data. The payload schema is defined in [schemas.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/api/v1/schemas.py#L354). The endpoint accepts these parameters.

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

This response confirms the call succeeded, but let's do something more with the returned answer from the agent.

This example creates a question-and-answer chat in your terminal, and stores the previous answer. To view the previous answer, type `compare`.

<details open>

<summary>Python</summary>

<CodeBlock language="Python" title="examples/get-started.py">{getStartedPython}</CodeBlock>

</details>

</TabItem>

<TabItem value="JavaScript" label="JavaScript">

<CodeBlock language="JavaScript" title="examples/playground-default.js">{playgroundJavascriptCode}</CodeBlock>

The `url` value at the `/api/v1/run/` endpoint is the endpoint your application passes the values in `payload` to.
The `payload` is the request data. The payload schema is defined in [schemas.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/api/v1/schemas.py#L354). The endpoint accepts these parameters.

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

This response confirms the call succeeded, but let's do something more with the returned answer from the agent.

This example creates a question-and-answer chat in your terminal, and stores the previous answer. To view the previous answer, type `compare`.

<CodeBlock language="JavaScript" title="examples/get-started.js">{getStartedJavascript}</CodeBlock>

</TabItem>

<TabItem value="curl" label="curl">

To make a curl request to the /api/v1/run endpoint, copy the code in the curl tab to your terminal and run it.
For example:
```curl
curl --request POST \
     --url 'http://localhost:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6?stream=false' \
     --header 'Content-Type: application/json' \
     --data '{
		           "output_type": "chat",
		           "input_type": "chat",
		           "input_value": "hello world!"
		         }'
```

<details open>
<summary>Result</summary>

```json
{"session_id":"29deb764-af3f-4d7d-94a0-47491ed241d6","outputs":[{"inputs":{"input_value":"hello world!"},"outputs":[{"results":{"message":{"text_key":"text","data":{"timestamp":"2025-06-16 15:27:48 UTC","sender":"Machine","sender_name":"AI","session_id":"29deb764-af3f-4d7d-94a0-47491ed241d6","text":"Hello! How can I assist you today? 😊","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"Agent-ZOknz","display_name":"Agent","source":"gpt-4.1"},"icon":"bot","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[{"title":"Agent Steps","contents":[{"type":"text","duration":1,"header":{"title":"Input","icon":"MessageSquare"},"text":"**Input**: hello world!"},{"type":"text","duration":104,"header":{"title":"Output","icon":"MessageSquare"},"text":"Hello! How can I assist you today? 😊"}],"allow_markdown":true,"media_url":null}],"id":"7d743965-88bc-4f1d-8bdf-1d69b27f8a8d","flow_id":"29deb764-af3f-4d7d-94a0-47491ed241d6","duration":null},"default_value":"","text":"Hello! How can I assist you today? 😊","sender":"Machine","sender_name":"AI","files":[],"session_id":"29deb764-af3f-4d7d-94a0-47491ed241d6","timestamp":"2025-06-16T15:27:48+00:00","flow_id":"29deb764-af3f-4d7d-94a0-47491ed241d6","error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"Agent-ZOknz","display_name":"Agent","source":"gpt-4.1"},"icon":"bot","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[{"title":"Agent Steps","contents":[{"type":"text","duration":1,"header":{"title":"Input","icon":"MessageSquare"},"text":"**Input**: hello world!"},{"type":"text","duration":104,"header":{"title":"Output","icon":"MessageSquare"},"text":"Hello! How can I assist you today? 😊"}],"allow_markdown":true,"media_url":null}],"duration":null}},"artifacts":{"message":"Hello! How can I assist you today? 😊","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"outputs":{"message":{"message":"Hello! How can I assist you today? 😊","type":"text"}},"logs":{"message":[]},"messages":[{"message":"Hello! How can I assist you today? 😊","sender":"Machine","sender_name":"AI","session_id":"29deb764-af3f-4d7d-94a0-47491ed241d6","stream_url":null,"component_id":"ChatOutput-aF5lw","files":[],"type":"text"}],"timedelta":null,"duration":null,"component_display_name":"Chat Output","component_id":"ChatOutput-aF5lw","used_frozen_result":false}]}]}%  
```
</details>

This response confirms the call succeeded.

</TabItem>
</Tabs>

## Apply tweaks to the flow

What if you want to make changes to the flow's components programmatically? For example, you want to use a different LLM provider in the Agent component.

Langflow includes a feature c





