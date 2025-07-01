---
title: Use the visual editor
slug: /concepts-overview
---

import Icon from "@site/src/components/icon";

Langflow's visual editor helps you create flows in minutes.
The drag-and-drop interface allows developers to create complex AI workflows without writing extensive code.

You can connect different resources, including prompts, large language models (LLMs), data sources, agents, MCP servers, and more.

:::tip
To try building and running a flow in a few minutes, see the [Langflow quickstart](/get-started-quickstart).
:::

## Visual editor

You use Langflow's visual editor to create, test, and share flows.

When building a flow, you primarily interact with the **Workspace**.
Additional testing, debugging, and sharing tools are available through the **Workspace**.

### Workspace

The **Workspace** is where you build your flows by adding components, configuring them, and attaching them together.

![Empty langflow workspace](/img/workspace.png)

#### Workspace gestures and interactions

- To pan horizontally and vertically, click and drag an empty area of the workspace.
- To visually rearrange components, click and drag each component.
However, you must use component ports to determine the sequence and relationship between components.
For more information, see [Components overview](/concepts-components).
- To lock the visual position of the components, click <Icon name="LockOpen" aria-hidden="true"/> **Lock**.
- To zoom, you can scroll, click <Icon name="ZoomIn" aria-hidden="true"/> **Zoom In** and <Icon name="ZoomOut" aria-hidden="true"/> **Zoom Out**, or click <Icon name="Maximize" aria-hidden="true"/> **Fit To Zoom** to scale the zoom level to show the entire flow.
- To add a text box for non-functional notes and comments, click <Icon name="StickyNote" aria-hidden="true"/> **Add Note**.

### Playground

From the **Workspace**, click <Icon name="Play" aria-hidden="true"/> **Playground** to test your flow.

If your flow has a **Chat Input** component, you can use the **Playground** to run your flow, chat with your flow, view inputs and outputs, and modify your AI's memories to tune your responses in real time.

For example, if your flow has **Chat Input**, **Language Model**, and **Chat Output** components, then you can chat with the LLM in the **Playround** to test the flow.
To try this for yourself, you can use the [**Basic Prompting** template](/basic-prompting).

![Playground window](/img/playground.png)

If you have an **Agent** component in your flow, the **Playground** displays its tool calls and outputs so you can monitor the agent's tool use and understand the reasoning behind its responses.
To try this for yourself, you can use the [**Simple Agent** template](/simple-agent).

<!-- ![Playground window with agent response](/img/playground-with-agent.png) -->

For more information, see [Playground](/concepts-playground).

### Share {#share-menu}

The **Share** menu provides the following options for integrating your flow into external applications:

* [**API access**](/concepts-publish#api-access): Integrate your flow into your applications with automatically-generated Python, JavaScript, and curl code snippets.
* [**Export**](/concepts-flows-import#export-a-flow): Export your flow to your local machine as a JSON file.
* [**MCP Server**](/mcp-server): Expose your flow as a tool for MCP-compatible clients.
* [**Embed into site**](/embedded-chat-widget): Embed your flow in HTML, React, or Angular applications.
<!-- * [**Shareable playground**](/concepts-publish#shareable-playground): Share your **Playground** interface with another user. This is specifically for sharing the **Playground** experience; it isn't for running a flow in a production application. -->

## Langflow settings

In the Langflow header, click your profile icon, and then select **Settings** to access general Langflow settings, including [global variables](/configuration-global-variables), [Langflow API keys](configuration-api-keys), keyboard shortcuts, and log messages.

## See also

* [Manage files](/concepts-file-management): Upload, store, and manage files in Langflow's file management system.