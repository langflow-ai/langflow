---
title: Use the visual editor
slug: /concepts-overview
---

import Icon from "@site/src/components/icon";

You use Langflow's visual editor to create, test, and share flows.

The drag-and-drop interface allows you to create complex AI workflows without writing extensive code.
You can connect different resources, including prompts, large language models (LLMs), data sources, agents, MCP servers, and other tools and integrations.

:::tip
To try building and running a flow in a few minutes, see the [Langflow quickstart](/get-started-quickstart).
:::

## Workspace

When building a flow, you primarily interact with the **Workspace**.
This is where you add components, configure them, and attach them together.

![Empty langflow workspace](/img/workspace.png)

From the **Workspace**, you can also access the [**Playground**](#playground), [**Share** menu](#share-menu), and [flow logs](/concepts-flows#flow-logs).

### Workspace gestures and interactions

- To pan horizontally and vertically, click and drag an empty area of the workspace.

- To rearrange components visually, click and drag the components.

    To change the programmatic relationship between components, you must manipulate the component _edges_ or _ports_. For more information, see [Components overview](/concepts-components).

- To lock the visual position of the components, click <Icon name="LockOpen" aria-hidden="true"/> **Lock**.

- To zoom, use any of the following options:
   - Scroll up or down on the mouse or trackpad
   - Click <Icon name="ZoomIn" aria-hidden="true"/> **Zoom In** or <Icon name="ZoomOut" aria-hidden="true"/> **Zoom Out**
   - Click <Icon name="Maximize" aria-hidden="true"/> **Fit To Zoom** to scale the zoom level to show the entire flow.

- To add a text box for non-functional notes and comments, click <Icon name="StickyNote" aria-hidden="true"/> **Add Note**.

## Playground

From the **Workspace**, click <Icon name="Play" aria-hidden="true"/> **Playground** to test your flow.

If your flow has a **Chat Input** component, you can use the **Playground** to run your flow, chat with your flow, view inputs and outputs, and modify your AI's memories to tune your responses in real time.

For example, if your flow has **Chat Input**, **Language Model**, and **Chat Output** components, then you can chat with the LLM in the **Playround** to test the flow.
To try this for yourself, you can use the [**Basic Prompting** template](/basic-prompting).

![Playground window](/img/playground.png)

If you have an **Agent** component in your flow, the **Playground** displays its tool calls and outputs so you can monitor the agent's tool use and understand the reasoning behind its responses.
To try this for yourself, you can use the [**Simple Agent** template](/simple-agent).

<!-- ![Playground window with agent response](/img/playground-with-agent.png) -->

For more information, see [Playground](/concepts-playground).

## Share {#share-menu}

The **Share** menu provides the following options for integrating your flow into external applications:

* [**API access**](/concepts-publish#api-access): Integrate your flow into your applications with automatically-generated Python, JavaScript, and curl code snippets.
* [**Export**](/concepts-flows-import#export-a-flow): Export your flow to your local machine as a JSON file.
* [**MCP Server**](/mcp-server): Expose your flow as a tool for MCP-compatible clients.
* [**Embed into site**](/embedded-chat-widget): Embed your flow in HTML, React, or Angular applications.
<!-- * [**Shareable playground**](/concepts-publish#shareable-playground): Share your **Playground** interface with another user. This is specifically for sharing the **Playground** experience; it isn't for running a flow in a production application. -->

## See also

* [Manage files](/concepts-file-management): Upload, store, and manage files in Langflow's file management system.
* [Global variables](/configuration-global-variables)
* [Langflow API keys](configuration-api-keys)