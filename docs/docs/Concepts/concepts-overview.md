---
title: Langflow overview
slug: /concepts-overview
---

import Icon from "@site/src/components/icon";

This page explores the fundamental building blocks of Langflow, beginning with the question, **"What is a flow?"**

## What is a flow?

A **flow** is an application. It receives input, processes it, and produces output.

Flows are created in the **workspace** with components dragged from the components sidebar.

![Basic prompting flow within in the workspace](/img/workspace-basic-prompting.png)

A flow can be as simple as the [basic prompting flow](/get-started-quickstart), which creates an OpenAI chatbot with four components.

- Each component in a flow is a **node** that performs a specific task, like an AI model or a data source.
- Each component has a **Configuration** menu. Click the <Icon name="Code" aria-hidden="true"/> **Code** button on a component to see its underlying Python code.
- Components are connected with **edges** to form flows.

If you're familiar with [React Flow](https://reactflow.dev/learn), a **flow** is a node-based application, a **component** is a node, and the connections between components are **edges**.

When a flow is run, Langflow builds a Directed Acyclic Graph (DAG) graph object from the nodes (components) and edges (connections between components), with the nodes sorted to determine the order of execution. The graph build calls the individual components' `def_build` functions to validate and prepare the nodes. This graph is then processed in dependency order. Each node is built and executed sequentially, with results from each built node being passed to nodes that are dependent on the previous node's results.

Flows are stored on local disk at the following default locations:

- **Linux and WSL**: `home/<username>/.cache/langflow/`
- **macOS**: `/Users/<username>/Library/Caches/langflow/`
- **Windows**: `%LOCALAPPDATA%\langflow\langflow\Cache`

The flow storage location can be customized with the [LANGFLOW_CONFIG_DIR](/environment-variables#LANGFLOW_CONFIG_DIR) environment variable.

## Find your way around

If you're new to Langflow, it's OK to feel a bit lost at first. We’ll take you on a tour, so you can orient yourself and start creating applications quickly.

Langflow has four distinct regions: the [workspace](#workspace) is the main area where you build your flows. The components sidebar is on the left, and lists the available [components](#components). The [playground](#playground) and [Share menu](#share-menu) are available in the upper right corner.

## Workspace

The **workspace** is where you create AI applications by connecting and running components in flows.

- Click and drag the workspace to move it left, right, up, and down.
- Scroll up and down to zoom in and out of the workspace, or use the <Icon name="ZoomIn" aria-hidden="true"/> **Zoom In** and <Icon name="ZoomOut" aria-hidden="true"/> **Zoom Out** controls.
- Click <Icon name="Maximize" aria-hidden="true"/> **Fit To Zoom** to center the workspace on the current flow.
- Click <Icon name="StickyNote" aria-hidden="true"/> **Add Note** to add a note to your flow, similar to commenting in code.
- Click <Icon name="LockOpen" aria-hidden="true"/> **Lock** to lock the workspace in place, preventing accidental movement.

![Empty langflow workspace](/img/workspace.png)

## Components

A **component** is a single building block within a flow and consists of inputs, outputs, and parameters that define its functionality.

To add a component to your flow, drag it from the sidebar onto the workspace.

To connect components, drag a line from the output handle (<Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4f46e5', fill: '#4f46e5' }}/>) of a component to the input handle of the same color (<Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4f46e5', fill: '#4f46e5' }}/>) of another.

For example, to connect **Chat Input**, **Language Model**, and **Chat Output** components, connect the blue **Message** handles to each other:

![Chat input and output connected to Language model component](/img/connect-component.png)

**Message** handles send text strings between components, so these components send text to each other.
Additional data types include **Data** (<Icon name="Circle" size="16" aria-label="A red circle on the side of a component" style={{ color: '#ef4444', fill: '#ef4444' }}/>) and **DataFrame** (<Icon name="Circle" size="16" aria-label="A red circle on the side of a component" style={{ color: '#d72670', fill: '#d72670' }}/>).

For more information, see [Components](/concepts-components).

## Playground

If a **Chat Input** component is in your current flow, the **Playground** enables you to run your flow, chat with your flow, view inputs and outputs, and modify your AI's memories to tune your responses in real time.

For example, click <Icon name="Play" aria-hidden="true"/> **Playground** in a flow that includes **Chat Input**, **Language Model**, and **Chat Output** components to chat with the LLM.

![Playground window](/img/playground.png)

If you have an **Agent** in your flow, the **Playground** displays its tool calls and outputs, so you can monitor the agent's tool use and understand how it came to the answer it returns.

![Playground window with agent response](/img/playground-with-agent.png)

For more information, see [Playground](/concepts-playground).

## Share {#share-menu}

The **Share** menu provides options for integrating your flow into external applications.

For more information, see the links below.

* [API access](/concepts-publish#api-access) - Code snippets to run your flow with Python, JavaScript, or curl.
* [Export](/concepts-flows#export-flow) - Export your flow to your local machine as a JSON file.
* [MCP Server](/mcp-server) - Expose your flow as a tool for MCP-compatible clients.
* [Embed into site](/embedded-chat-widget) - Embed your flow in HTML, React, or Angular applications.
* [Shareable playground](/concepts-publish#shareable-playground) - Share your **Playground** interface with another user.

## View logs

The **Logs** pane provides a detailed record of all component executions within a workspace.

To access the **Logs** pane, click **Logs**.

![Logs pane](/img/logs.png)

Langflow stores logs at the location specified in the `LANGFLOW_CONFIG_DIR` environment variable.

This directory's default location depends on your operating system.

- **Linux and WSL**: `~/.cache/langflow/`
- **macOS**: `/Users/<username>/Library/Caches/langflow/`
- **Windows**: `%LOCALAPPDATA%\langflow\langflow\Cache`

To modify the location of your log file:

1. Add `LANGFLOW_LOG_FILE=path/to/logfile.log` in your `.env` file.
2. To start Langflow with the values from your `.env` file, start Langflow with `uv run langflow run --env-file .env`.

An example `.env` file is available in the [project repository](https://github.com/langflow-ai/langflow/blob/main/.env.example).

## Projects

The **Projects** page displays all the flows you've created in the Langflow workspace.

![](/img/my-projects.png)

**Starter Project** is the default space where all new projects are initially stored.
To create a new project, click <Icon name="Plus"aria-hidden="true"/> **Create new project**.

To upload a flow to your project, click <Icon name="Upload" aria-hidden="true"/> **Upload a flow**.

To delete a flow from your project, click a flow's checkbox to select it, and then click <Icon name="Trash2" aria-hidden="true"/> **Delete**.
You can select multiple flows in a single action.

## File management

Upload, store, and manage files in Langflow's **File management** system.

For more on managing your files, see [Manage files](/concepts-file-management).

## Settings

Click <Icon name="Settings" aria-hidden="true"/> **Settings** to access **Global variables**, **MCP Servers**, **Langflow API keys**, **Shortcuts**, and **Messages**.
