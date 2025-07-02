---
title: Publish flows
slug: /concepts-publish
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import ChatWidget from '@site/src/components/ChatWidget';

Langflow provides several ways to publish and integrate your flows into external applications. Whether you want to expose your flow as an API endpoint, embed it as a chat widget in your website, or share it as a public playground, this guide covers the options available for making your flows accessible to users.

## Use the Langflow API to run flows

Langflow provides Python, JavaScript, and curl code snippets to help you get started with the Langflow API.

These code snippets are available on each flow's **API access** pane.
To access the **API access** pane, click **Share**, and then click **API access**.

![API access pane](/img/api-pane.png)

You can run the snippet as is, or use the snippet as a basis for a larger script.

For more information and examples, see [Run your flows from external applications](/get-started-quickstart#run-your-flows-from-external-applications) and [Get started with the Langflow API](/api-reference-api-examples).

### Authentication

<!-- TODO Link to api key page -->

### Input schema and tweaks

<!-- TODO: Revise this section and combine w/ temp overrides section -->

Tweaks are added to the `payload` of requests to Langflow's `/run` endpoint to temporarily change component parameters within your flow.
They don't modify the underlying flow configuration or persist between runs.

To assist with formatting, you can define tweaks in Langflow's **Input Schema** pane before copying the code snippet.

For more information, see [Use tweaks to apply temporary overrides to a flow run](/get-started-quickstart#use-tweaks-to-apply-temporary-overrides-to-a-flow-run).

### Temporary overrides and tweaks

The **Temporary overrides** tab displays flow parameters that you can modify at runtime.

Modifying these parameters changes those values across all code snippets.
However, these changes don't persist into the visual editor, and they aren't saved.

For example, changing the **Chat Input** component's `input_value` changes that value across all API `/run` code snipepts.

For more information, see the tweaks example in the [Langflow quickstart](/get-started-quickstart#use-tweaks-to-apply-temporary-overrides-to-a-flow-run).

### Send files to your flow with the API

For information on sending files to the Langflow API, see [Files endpoint](/api-files).

## Share a Langflow MCP server

<!-- TODO: Add link to projects page & reconcile dupliation w mcp server page -->
Each Langflow project has an MCP server that exposes the project's flows as tools that MCP clients can use to generate responses.

You can also use Langflow as an MCP client, and you can serve your flows as tools to the Langflow MCP client.

For more information, see [Use Langflow as an MCP server](/mcp-server) and [Use Langflow as an MCP client](/mcp-client).

## Share a flow's Playground

<!-- TODO: get the content from the quick guide deploy PR

The **Shareable playground** option exposes the **Playground** for a single flow at the `/public_flow/{flow-id}` endpoint.
	
	This allows you to share a public URL with another user that displays only the **Playground** chat window for the specified flow.
	
	The user can interact with the flow's chat input and output and view the results without requiring a Langflow installation or API keys of their own.

:::important
	The **Sharable Playground** is for testing purposes only. 
	
	The **Playground** isn't meant for embedding flows in applications. For information about running flows in applications or websites, see [About developing and configuring Langflow applications](/develop-overview) and [Publish flows](/concepts-publish).
	:::

To share a flow's **Playground** with another user, do the following:

1. In Langflow, open the flow you want share.
	2. From the **Workspace**, click **Share**, and then enable **Shareable Playground**.

3. Click **Shareable Playground** again to open the **Playground** window.
This window's URL is the flow's **Sharable Playground** address, such as `https://3f7c-73-64-93-151.ngrok-free.app/playground/d764c4b8-5cec-4c0f-9de0-4b419b11901a`.

4. Send the URL to another user to give them access to the flow's **Playground**.
-->

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/$FLOW_ID` endpoint.

You can share this endpoint publicly using a sharing platform like [ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).

## Embed a flow into a website

<!-- TODO:Combine external chat widget page -->

The **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

For more information, see [Embedded chat widget](/embedded-chat-widget).

## See also

* [Develop an application with Langflow](/develop-application)
* [Langflow deployment overview](/deployment-overview)
* [Import and export flows](/concepts-flows-import)