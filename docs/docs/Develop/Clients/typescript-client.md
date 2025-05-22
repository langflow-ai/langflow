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

## Import the Langflow Typescript package

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

## Use the Langflow TypeScript client


