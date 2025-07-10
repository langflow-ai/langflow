---
title: Share flows
slug: /concepts-publish
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow provides several ways to publish and integrate your flows into external applications. Whether you want to expose your flow as an API endpoint, embed it as a chat widget in your website, or share it as a public playground, this guide covers the options available for making your flows accessible to users.

## API access

Langflow provides code snippets to help you get started with the Langflow API.

As of Langflow version 1.5, all API requests require authentication with a Langflow API key, even if `AUTO_LOGIN` is set to `True`.
For more information, see [API keys](/configuration-api-keys).
The API access pane’s code snippets include a script that looks for a `LANGFLOW_API_KEY` environment variable set in your terminal session.
To set this variable in your terminal:
```bash
export LANGFLOW_API_KEY="sk..."
```

![API pane](/img/api-pane.png)

For more information, see [Run your flows from external applications](/get-started-quickstart#run-your-flows-from-external-applications).

### Input schema

Tweaks are added to the `payload` of requests to Langflow's `/run` endpoint to temporarily change component parameters within your flow.
They don't modify the underlying flow configuration or persist between runs.
To assist with formatting, you can define tweaks in Langflow's **Input Schema** pane before copying the code snippet.

For more information, see [Use tweaks to apply temporary overrides to a flow run](/get-started-quickstart#use-tweaks-to-apply-temporary-overrides-to-a-flow-run).

Additionally, you can re-name your flow's API endpoint from the default UUID to a more memorable and user-friendly name.

To set a custom endpoint name:
1. In the **Input Schema** pane, locate the **Endpoint Name** field.
2. Enter a name using only letters, numbers, hyphens, and underscores.
The endpoint name is automatically saved with your flow.

## Export

**Export** a flow to download it as a JSON file to your local machine.

1. To **Export** your flow, in the **Playground**, click **Share**, and then click **Export**.
2. To save your API keys with the flow, select **Save with my API keys**.
Your flow is saved with any Global variables included.

:::important
If your key is saved as a Global variable, only the global variable you created to contain the value is saved. If your key value is manually entered into a component field, the actual key value is saved in the JSON file.
:::

When you share your flow file with another user who has the same global variables populated, the flow runs without requiring keys to be added again.

The `FLOW_NAME.json` file is downloaded to your local machine.

You can then **Import** the downloaded flow into another Langflow instance.

## MCP server

**MCP server** exposes your flows as [tools](https://modelcontextprotocol.io/docs/concepts/tools) that [MCP clients](https://modelcontextprotocol.io/clients) can use to take actions.

For more information, see [MCP server](/mcp-server).

For information about using Langflow as an *MCP client*, see [MCP client](/mcp-client).

## Embed into site

The **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

For more information, see [Embedded chat widget](/embedded-chat-widget).

## Shareable playground

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/$FLOW_ID` endpoint.

You can share this endpoint publicly using a sharing platform like [ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).