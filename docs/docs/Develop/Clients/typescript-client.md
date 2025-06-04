---
title: Langflow TypeScript client
slug: /typescript-client
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

The Langflow TypeScript client allows your TypeScript applications to programmatically interact with the Langflow API.

For the client code repository, see [langflow-client-ts](https://github.com/datastax/langflow-client-ts/).

For the npm package, see [@datastax/langflow-client](https://www.npmjs.com/package/@datastax/langflow-client).

## Install the Langflow TypeScript package

To install the Langflow typescript client package, use one of the following commands:

<Tabs groupId="package-manager">
<TabItem value="npm" label="npm" default>

```bash
npm install @datastax/langflow-client
```

</TabItem>
<TabItem value="yarn" label="yarn">

```bash
yarn add @datastax/langflow-client
```

</TabItem>
<TabItem value="pnpm" label="pnpm">

```bash
pnpm add @datastax/langflow-client
```

</TabItem>
</Tabs>

## Initialize the Langflow TypeScript client

1. Import the client into your code.

```tsx
import { LangflowClient } from "@datastax/langflow-client";
```

2. Initialize a client object to interact with your server.
The `LangflowClient` object allows you to interact with the Langflow API.

Replace `BASE_URL` and `API_KEY` with values from your deployment.
The default Langflow base URL is `http://localhost:7860`.
To create an API key, see [API keys](/configuration-api-keys).

```tsx
const baseUrl = "BASE_URL";
const apiKey = "API_KEY";
const client = new LangflowClient({ baseUrl, apiKey });
```

## Langflow TypeScript client quickstart

1. With your Langflow client initialized, submit a message to your Langflow server and receive a response.
This example uses the minimum values for sending a message and running your flow on a Langflow server, with no API keys.
Replace `baseUrl` and `flowId` with values from your deployment.
The `input` string is the message you're sending to your flow.

```tsx
import { LangflowClient } from "@datastax/langflow-client";

const baseUrl = "http://127.0.0.1:7860";
const client = new LangflowClient({ baseUrl });

async function runFlow() {
    const flowId = "aa5a238b-02c0-4f03-bc5c-cc3a83335cdf";
    const flow = client.flow(flowId);
    const input = "Is anyone there?";

    const response = await flow.run(input);
    console.log(response);
}

runFlow().catch(console.error);
```

<details open>
<summary>Response</summary>

```
FlowResponse {
  sessionId: 'aa5a238b-02c0-4f03-bc5c-cc3a83335cdf',
  outputs: [ { inputs: [Object], outputs: [Array] } ]
}
```

</details>

This confirms your client is connecting to Langflow.
* The `sessionID` value is a unique identifier for the client-server session. For more information, see [Session ID](/session-id).
* The `outputs` array contains the results of your flow execution.

2. To get the full response objects from your server, change the `console.log` code to stringify the returned JSON object:

```tsx
console.log(JSON.stringify(response, null, 2));
```

The exact structure of the returned `inputs` and `outputs` depends on how your flow is configured in Langflow.

3. To get the first chat message returned from the chat output component, change `console.log` to use the `chatOutputText` convenience function.

```tsx
console.log(response.chatOutputText());
```

## Use advanced TypeScript client features

The TypeScript client can do more than just connect to your server and run a flow.

This example builds on the quickstart with additional features for interacting with Langflow.

1. Pass tweaks to your code as an object with the request.
Tweaks change values within components for all calls to your flow.
This example tweaks the Open-AI model component to enforce using the `gpt-4o-mini` model.
```tsx
const tweaks = { model_name: "gpt-4o-mini" };
```
2. Pass a session ID with the request to maintain the same conversation with the LLM from this application.
```tsx
const session_id = "aa5a238b-02c0-4f03-bc5c-cc3a83335cdf";
```
3. Instead of calling `run` on the Flow object, call `stream` with the same arguments.
The response is a [ReadableStream](https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream) of objects.
For more information on streaming Langflow responses, see [Run flow](https://docs.langflow.org/api-reference-api-examples#run-flow).
```tsx
const response = await client.flow(flowId).stream(input);

for await (const event of response) {
  console.log(event);
}
```
4. Run the completed TypeScript application to call your server with `tweaks` and `session_id`, and stream the response back.
Replace `baseUrl` and `flowId` with values from your deployment.

```tsx
import { LangflowClient } from "@datastax/langflow-client";

const baseUrl = "http://127.0.0.1:7860";
const client = new LangflowClient({ baseUrl });

async function runFlow() {
    const flowId = "aa5a238b-02c0-4f03-bc5c-cc3a83335cdf";
    const input = "Is anyone there?";
    const tweaks = { model_name: "gpt-4o-mini" };
    const session_id = "test-session";

    const response = await client.flow(flowId).stream(input, {
        session_id,
        tweaks,
      });

    for await (const event of response) {
        console.log(event);
    }

}
runFlow().catch(console.error);
```

<details>
<summary>Response</summary>

```text
{
  event: 'add_message',
  data: {
    timestamp: '2025-05-23 15:52:48 UTC',
    sender: 'User',
    sender_name: 'User',
    session_id: 'test-session',
    text: 'Is anyone there?',
    files: [],
    error: false,
    edit: false,
    properties: {
      text_color: '',
      background_color: '',
      edited: false,
      source: [Object],
      icon: '',
      allow_markdown: false,
      positive_feedback: null,
      state: 'complete',
      targets: []
    },
    category: 'message',
    content_blocks: [],
    id: '7f096715-3f2d-4d84-88d6-5e2f76bf3fbe',
    flow_id: 'aa5a238b-02c0-4f03-bc5c-cc3a83335cdf',
    duration: null
  }
}
{
  event: 'token',
  data: {
    chunk: 'Absolutely',
    id: 'c5a99314-6b23-488b-84e2-038aa3e87fb5',
    timestamp: '2025-05-23 15:52:48 UTC'
  }
}
{
  event: 'token',
  data: {
    chunk: ',',
    id: 'c5a99314-6b23-488b-84e2-038aa3e87fb5',
    timestamp: '2025-05-23 15:52:48 UTC'
  }
}
{
  event: 'token',
  data: {
    chunk: " I'm",
    id: 'c5a99314-6b23-488b-84e2-038aa3e87fb5',
    timestamp: '2025-05-23 15:52:48 UTC'
  }
}
{
  event: 'token',
  data: {
    chunk: ' here',
    id: 'c5a99314-6b23-488b-84e2-038aa3e87fb5',
    timestamp: '2025-05-23 15:52:48 UTC'
  }
}

// this response is abbreviated

{
  event: 'end',
  data: { result: { session_id: 'test-session', outputs: [Array] } }
}
```

</details>

## Retrieve Langflow logs with the TypeScript client

To retrieve Langflow logs, you must enable log retrieval on your Langflow server by including the following values in your server's `.env` file:

```text
LANGFLOW_ENABLE_LOG_RETRIEVAL=true
LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE=10000
LANGFLOW_LOG_LEVEL=DEBUG
```

For more information, see [API examples](/api-reference-api-examples#logs).

This complete example starts streaming logs in the background, and then runs a flow so you can see how a flow executes.
Replace `baseUrl` and `flowId` with values from your deployment.

```tsx
import { LangflowClient } from "@datastax/langflow-client";

const baseUrl = "http://127.0.0.1:7863";
const flowId = "86f0bf45-0544-4e88-b0b1-8e622da7a7f0";

async function runFlow(client: LangflowClient) {
    const input = "Is anyone there?";
    const response = await client.flow(flowId).run(input);
    console.log('Flow response:', response);
}

async function main() {
    const client = new LangflowClient({ baseUrl: baseUrl });

    // Start streaming logs
    console.log('Starting log stream...');
    for await (const log of await client.logs.stream()) {
        console.log('Log:', log);
    }

    // Run the flow
    await runFlow(client);

}

main().catch(console.error);
```

Logs begin streaming indefinitely, and the flow runs once.

The logs below are abbreviated, but you can monitor how the flow instantiates its components, configures its model, and processes the outputs.

<details>
<summary>Response</summary>

```text
Starting log stream...
Log: Log {
  timestamp: 2025-05-30T11:49:16.006Z,
  message: '2025-05-30T07:49:16.006127-0400 DEBUG Instantiating ChatInput of type component\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.029Z,
  message: '2025-05-30T07:49:16.029957-0400 DEBUG Instantiating Prompt of type component\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.049Z,
  message: '2025-05-30T07:49:16.049520-0400 DEBUG Instantiating ChatOutput of type component\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.069Z,
  message: '2025-05-30T07:49:16.069359-0400 DEBUG Instantiating OpenAIModel of type component\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.086Z,
  message: "2025-05-30T07:49:16.086426-0400 DEBUG Running layer 0 with 2 tasks, ['ChatInput-xjucM', 'Prompt-I3pxU']\n"
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.101Z,
  message: '2025-05-30T07:49:16.101766-0400 DEBUG Building Chat Input\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.113Z,
  message: '2025-05-30T07:49:16.113343-0400 DEBUG Building Prompt\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.131Z,
  message: '2025-05-30T07:49:16.131423-0400 DEBUG Logged vertex build: 6bd9fe9c-5eea-4f05-a96d-f6de9dc77e3c\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.143Z,
  message: '2025-05-30T07:49:16.143295-0400 DEBUG Logged vertex build: 39c68ec9-3859-4fff-9b14-80b3271f8fbf\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.188Z,
  message: "2025-05-30T07:49:16.188730-0400 DEBUG Running layer 1 with 1 tasks, ['OpenAIModel-RtlZm']\n"
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.201Z,
  message: '2025-05-30T07:49:16.201946-0400 DEBUG Building OpenAI\n'
}
Log: Log {
  timestamp: 2025-05-30T11:49:16.216Z,
  message: '2025-05-30T07:49:16.216622-0400 INFO Model name: gpt-4.1-mini\n'
}
Flow response: FlowResponse {
  sessionId: '86f0bf45-0544-4e88-b0b1-8e622da7a7f0',
  outputs: [ { inputs: [Object], outputs: [Array] } ]
}
Log: Log {
  timestamp: 2025-05-30T11:49:18.094Z,
  message: `2025-05-30T07:49:18.094364-0400 DEBUG Vertex OpenAIModel-RtlZm, result: <langflow.graph.utils.UnbuiltResult object at 0x364d24dd0>, object: {'text_output': "Hey there! I'm here and ready to help you build something awesome with AI. What are you thinking about creating today?"}\n`
}
```

</details>

The `FlowResponse` object is returned to the client, with the `outputs` array including your flow result.

## Langflow TypeScript project repository

You can do even more with the Langflow TypeScript client.

For more information, see the [langflow-client-ts](https://github.com/datastax/langflow-client-ts/) repository.