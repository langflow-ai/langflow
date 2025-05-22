---
title: Langflow TypeScript client
slug: /typescript-client
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

For more information, see the [langflow-client-ts](https://github.com/datastax/langflow-client-ts/) repository.

## Install the Langflow TypeScript package

To install Langflow, use one of the following commands:

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

## Initialize the Langflow Typescript client

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

## Run your flow with the Langflow TypeScript client

With your Langflow client initialized, you can do anything the API can do.

1. Create a reference to your flow with the `flowID` retrieved from Langflow.
```typescript
const flow = client.flow(flowId);
```

2. Run the referenced flow and pass text to it as `input`.
```typescript
const response = await client.flow(flowId).run(input);
```

3. This example uses the minimum values for sending a message and running your flow on a Langflow server, with no API keys.
<Tabs>
<TabItem value="TypeScript" label="TypeScript" default>

```typescript
import { LangflowClient } from "@datastax/langflow-client";

const baseUrl = "http://127.0.0.1:7860";
const client = new LangflowClient({ baseUrl });

async function runFlow() {
    const flowId = "aa5a238b-02c0-4f03-bc5c-cc3a83335cdf"; // Replace with your actual flow ID
    const input = "Is anyone there?"; // Replace with your actual input

    const flow = client.flow(flowId);
    const response = await client.flow(flowId).run(input);
    console.log(response);
}

runFlow().catch(console.error);
```

</TabItem>
<TabItem value="Response" label="Response">

```
FlowResponse {
  sessionId: 'aa5a238b-02c0-4f03-bc5c-cc3a83335cdf',
  outputs: [ { inputs: [Object], outputs: [Array] } ]
}
```

</TabItem>
</Tabs>

4. This confirms your client is connecting to Langflow.
The `sessionID` value is a unique identifier for the client-server session.
The `outputs` array contains the results of your flow execution.

5. To see the full response structure from your server, change the code to stringify the returned JSON object:

```typescript
console.log(JSON.stringify(response, null, 2));
```

The exact structure of `inputs` and `outputs` will depend on how your flow is configured in Langflow.

### 


