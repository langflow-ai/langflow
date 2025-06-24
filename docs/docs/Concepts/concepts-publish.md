---
title: Share flows
slug: /concepts-publish
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow provides several ways to publish and integrate your flows into external applications. Whether you want to expose your flow as an API endpoint, embed it as a chat widget in your website, or share it as a public playground, this guide covers the options available for making your flows accessible to users.

## API access

Langflow provides code snippets to help you get started with the Langflow API.

To access the **API access** pane, click **Share**, and then click **API access**.

![API pane](/img/api-pane.png)

For more information, see [Run your flows from external applications](/get-started-quickstart#run-your-flows-from-external-applications).

### Input schema

Tweaks are added to the `payload` of requests to Langflow's `/run` endpoint to temporarily change component parameters within your flow.
They don't modify the underlying flow configuration or persist between runs.
To assist with formatting, you can define tweaks in Langflow's **Input Schema** pane before copying the code snippet.

For more information, see [Use tweaks to apply temporary overrides to a flow run](/get-started-quickstart#use-tweaks-to-apply-temporary-overrides-to-a-flow-run).

## Export

**Export** a flow to download it as a JSON file to your local machine.

1. To **Export** your flow, in the **Playground**, click **Share**, and then click **Export**.
2. To save your API keys with the flow, select **Save with my API keys**.
You can then **Import** the downloaded flow into another Langflow instance.

## MCP server

**MCP server** exposes your flows as [tools](https://modelcontextprotocol.io/docs/concepts/tools) that [MCP clients](https://modelcontextprotocol.io/clients) can use use to take actions.

For more information, see [MCP server](/mcp-server).

For information about using Langflow as an *MCP client*, see [MCP client](/mcp-client).

## Embed into site

The **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

For more information, see [Embedded chat widget](/embedded-chat-widget).

## Shareable playground

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/$FLOW_ID` endpoint.

You can share this endpoint publicly using a sharing platform like [Ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).