---
title: Langflow TypeScript client
slug: /typescript-client
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

The Langflow TypeScript client integrates Langflow's capabilities into your TypeScript applications.

For more information, see the [langflow-client-ts](https://github.com/datastax/langflow-client-ts/) repository.

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

```typescript
import { LangflowClient } from "@datastax/langflow-client";
```

2. Initialize a client object to interact with your server.
The `osLangflowClient` object allows you to interact with the Langflow API.

Replace `BASE_URL` and `API_KEY` with values from your deployment.
The default Langflow base URL is `http://localhost:7860`.
To create an API key, see [API keys](/configuration-api-keys).

```typescript
const baseUrl = "BASE_URL";
const apiKey = "API_KEY";
const osLangflowClient = new LangflowClient({ baseUrl, apiKey });
```

## Run a flow with the Langflow TypeScript client

With your Langflow client initialized, submit a message to your Langflow server and receive a response.

1. Create a reference to your flow with the `flowID` retrieved from Langflow.
```typescript
const flow = client.flow(flowId);
```

2. Run the referenced flow and pass text to it as `input`.
```typescript
const response = await client.flow(flowId).run(input);
```

3. This example uses the minimum values for sending a message and running your flow on a Langflow server, with no API keys.
Replace `baseUrl` and `flowId` with values from your deployment.
The `input` string is the message you're sending to your flow.
<Tabs>
<TabItem value="TypeScript" label="TypeScript" default>

```typescript
import { LangflowClient } from "@datastax/langflow-client";

const baseUrl = "http://127.0.0.1:7860";
const client = new LangflowClient({ baseUrl });

async function runFlow() {
    const flowId = "aa5a238b-02c0-4f03-bc5c-cc3a83335cdf";
    const input = "Is anyone there?";

    const response = await client.flow(flowId).run(input);
    console.log(response);
}

runFlow().catch(console.error);
```

</TabItem>
</Tabs>

<details open>
<summary>Response</summary>

```
FlowResponse {
  sessionId: 'aa5a238b-02c0-4f03-bc5c-cc3a83335cdf',
  outputs: [ { inputs: [Object], outputs: [Array] } ]
}
```

</details>

4. This confirms your client is connecting to Langflow.
* The `sessionID` value is a unique identifier for the client-server session. For more information, see [Session ID](/session-id).
* The `outputs` array contains the results of your flow execution.

5. To get the full response objects from your server, change the `console.log` code to stringify the returned JSON object:

```typescript
console.log(JSON.stringify(response, null, 2));
```

The exact structure of the returned `inputs` and `outputs` depends on how your flow is configured in Langflow.

6. To get the first chat message returned from the chat output component, change `console.log` to use the `chatOutputText` convenience function.

```typescript
console.log(response.chatOutputText());
```

## Extend the starter example

The TypeScript client can do more than just connect to your server and run a flow.

This example adds additional features for interacting with Langflow.

1. Pass tweaks to your code as an object with the request.
Tweaks change values within components for all calls to your flow.
This example tweaks the Open-AI model component to enforce using the `gpt-4o-mini` model.
```typescript
const tweaks = { model_name: "gpt-4o-mini" };
```
2. Pass a session ID with the request to maintain the same conversation with the LLM from this application.
```typescript
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

<TabItem value="TypeScript" label="TypeScript" default>

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
</TabItem>

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



## Retrieve logs from Langflow

To retrieve Langflow logs, you must enable log retrieval on your Langflow server by including these values in your server's `.env` file:

```text
LANGFLOW_ENABLE_LOG_RETRIEVAL=true
LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE=10000
LANGFLOW_LOG_LEVEL=DEBUG
```

For more information, see [API examples](/api-reference-api-examples#logs).

```ts
import { LangflowClient } from "@datastax/langflow-client";

const baseUrl = "http://127.0.0.1:7860";
const client = new LangflowClient({ baseUrl });

const logs = await client.logs.fetch();
```