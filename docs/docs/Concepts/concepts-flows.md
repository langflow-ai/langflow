---
title: Create and manage flows
slug: /concepts-flows
---

import Icon from "@site/src/components/icon";

A _flow_ is a functional representation of an application. It receives input, processes it, and produces output.

Langflow flows are fully serializable and can be saved and loaded from the file system.

## Projects

The **Projects** page is where you arrive when you launch Langflow.
It is where you view and manage flows on a high level.

Langflow projects are like folders that you can use to organize related flows.
The default project is **Starter Project**, and your flows are stored here unless you create another project.

![](/img/my-projects.png)

To create a project, click <Icon name="Plus" aria-hidden="true"/> **Create new project**.

### Manage flows in projects

From the **Projects** page, you can manage flows within each of your projects:

* **View flows within a project**: Select the project name in the **Projects** list.
* **Create a new blank or template flow**: Select a project, and then click **New Flow**.
* **Create a flow by duplicating an existing flow**: Locate the flow you want to copy, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Duplicate**.
* **Edit a flow's name and description**: Locate the flow you want to edit, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Edit details**.
* **Delete a flow**: Locate the flow you want to delete, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Delete**.

## Components

Flows consist of [components](/concepts-components), which are nodes that you configure and connect in the Langflow [visual editor](/concepts-overview#visual-editor).
Each component performs a specific task, like serving an AI model or connecting a data source.

![Chat input and output connected to Language model component](/img/connect-component.png)

Each component has configuration settings and options. Some of these are common to all components, and some are unique to specific components.

You can edit components in the visual editor and in code. When editing a flow, select a component, and then click <Icon name="Code" aria-hidden="true"/> **Code** to see and edit the component's underlying Python code.

To form a cohesive flow, you connect components by _edges_ or _ports_, which have a specific data type they receive or send.
For example, message ports send text strings between components.

For more information about component configuration, including port types, see [Components overview](/concepts-components).

## Flow storage

Flows and [flow logs](#flow-logs) are stored on local disk at the following default locations:

- **Linux and WSL**: `home/<username>/.cache/langflow/`
- **macOS**: `/Users/<username>/Library/Caches/langflow/`
- **Windows**: `%LOCALAPPDATA%\langflow\langflow\Cache`

The flow storage location can be customized with the [`LANGFLOW_CONFIG_DIR`](/environment-variables#LANGFLOW_CONFIG_DIR) environment variable.

## Flow graphs

When a flow runs, Langflow builds a Directed Acyclic Graph (DAG) graph object from the nodes (components) and edges (connections), and the nodes are sorted to determine the order of execution.

The graph build calls each component's `def_build` function to validate and prepare the nodes.
This graph is then processed in dependency order.
Each node is built and executed sequentially, with results from each built node being passed to nodes that are dependent on that node's results.

## Flow logs

When viewing a flow in the **Workspace**, click **Logs** to examine logs for that flow and its components.

![Logs pane](/img/logs.png)

Langflow logs are stored in `.log` files in the same place as your flows.
For filepaths, see [Flow storage](/concepts-flows#flow-storage).

The flow storage location can be customized with the [`LANGFLOW_CONFIG_DIR`](/environment-variables#LANGFLOW_CONFIG_DIR) environment variable:

1. Add `LANGFLOW_LOG_FILE=path/to/logfile.log` in your `.env` file.

    An example `.env` file is available in the [Langflow repository](https://github.com/langflow-ai/langflow/blob/main/.env.example).

2. Start Langflow with the values from your `.env` file by running `uv run langflow run --env-file .env`.

## See also

* [Publish flows](/concepts-publish)
* [Import and export flows](/concepts-flows-import)