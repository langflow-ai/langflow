---
title: Langflow overview
slug: /concepts-overview
---

import Icon from "@site/src/components/icon";

This page introduces Langflow's key concepts, including projects, flows, and the visual editor.

:::tip
To try building and running a flow in a few minutes, see the [Langflow quickstart](/get-started-quickstart).
:::

## Flows

A _flow_ is a functional representation of an application. It receives input, processes it, and produces output.

![Basic prompting flow within in the workspace](/img/workspace-basic-prompting.png)

### Components

Flows consist of [components](/concepts-components), which are nodes that you configure and connect in the Langflow [visual editor](#visual-editor).
Each component performs a specific task, like serving an AI model or connecting a data source.

![Chat input and output connected to Language model component](/img/connect-component.png)

Each component has configuration settings and options. Some of these are common to all components, and some are unique to specific components.

You can edit components in the visual editor and in code. When editing a flow, select a component, and then click <Icon name="Code" aria-hidden="true"/> **Code** to see and edit the component's underlying Python code.

To form a cohesive flow, you connect components by _edges_ or _ports_, which have a specific data type they receive or send.
For example, message ports send text strings between components.

For more information about component configuration, including port types, see [Components overview](/concepts-components).

### Flow storage

Flows and [flow logs](#logs) are stored on local disk at the following default locations:

- **Linux and WSL**: `home/<username>/.cache/langflow/`
- **macOS**: `/Users/<username>/Library/Caches/langflow/`
- **Windows**: `%LOCALAPPDATA%\langflow\langflow\Cache`

The flow storage location can be customized with the [`LANGFLOW_CONFIG_DIR`](/environment-variables#LANGFLOW_CONFIG_DIR) environment variable.

### Flow graphs

When a flow runs, Langflow builds a Directed Acyclic Graph (DAG) graph object from the nodes (components) and edges (connections), and the nodes are sorted to determine the order of execution.

The graph build calls each component's `def_build` function to validate and prepare the nodes.
This graph is then processed in dependency order.
Each node is built and executed sequentially, with results from each built node being passed to nodes that are dependent on that node's results.

## Projects

The **Projects** page is where you arrive when you launch Langflow.
It is where you view and manage flows on a high level.

Langflow projects are like folders that you can use to organize related flows.
The default project is **Starter Project**, and your flows are stored here unless you create another project.

To create a project, click <Icon name="Plus" aria-hidden="true"/> **Create new project**.

To view flows within a project, select the project name in the **Projects** list.

![](/img/my-projects.png)

### Manage flows in projects

From the **Projects** page, you can manage flows within each of your projects:

* To create a new blank or template flow, select a project, and then click **New Flow**.
* To create a flow by duplicating an existing flow, locate the flow you want to copy, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Duplicate**.
* To edit a flow's name and description, locate the flow you want to edit, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Edit details**.
* To delete a flow,  locate the flow you want to delete, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Delete**.
* To import and export flows, see [Flows](/concepts-flows).

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
* [**Export**](/concepts-flows#export-flow): Export your flow to your local machine as a JSON file.
* [**MCP Server**](/mcp-server): Expose your flow as a tool for MCP-compatible clients.
* [**Embed into site**](/embedded-chat-widget): Embed your flow in HTML, React, or Angular applications.
<!-- * [**Shareable playground**](/concepts-publish#shareable-playground): Share your **Playground** interface with another user. This is specifically for sharing the **Playground** experience; it isn't for running a flow in a production application. -->

### Logs

From the **Workspace**, click **Logs** to examine records of component runs within that flow.
This can include full flow runs, partial runs, and individual component runs.

![Logs pane](/img/logs.png)

Langflow logs are stored in `.log` files in the same place as your flows.
For filepaths, see [Flow storage](#flow-storage).

The flow storage location can be customized with the [`LANGFLOW_CONFIG_DIR`](/environment-variables#LANGFLOW_CONFIG_DIR) environment variable:

1. Add `LANGFLOW_LOG_FILE=path/to/logfile.log` in your `.env` file.

    An example `.env` file is available in the [Langflow repository](https://github.com/langflow-ai/langflow/blob/main/.env.example).

2. Start Langflow with the values from your `.env` file by running `uv run langflow run --env-file .env`.

## File management

Upload, store, and manage files in Langflow's file management system.
For more information, see [Manage files](/concepts-file-management).

## Langflow settings

In the Langflow header, click your profile icon, and then select **Settings** to access general Langflow settings, including [global variables](/configuration-global-variables), [Langflow API keys](configuration-api-keys), keyboard shortcuts, and log messages.