---
title:  Use Langflow as an MCP client
slug: /mcp-client
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) as both an MCP server and an MCP client.

This page describes how to use Langflow as an MCP client with the [MCP Tools](#use-the-mcp-tools-component) component and the [MCP connections](#manage-mcp-connections) page in **Settings**.

For information about using Langflow as an MCP server, see [Use Langflow as an MCP server](/mcp-server).

## Use the MCP tools component

The **MCP Tools** component connects to a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server and exposes the MCP server's tools as tools for [Langflow agents](/agents).

This component has two modes, depending on the type of server you want to access:

* To access tools provided by external, non-Langflow MCP servers, [use JSON](#mcp-stdio-mode) or [Stdio mode](#mcp-stdio-mode).
* To use flows from your [Langflow projects](/concepts-overview#projects) as MCP tools, [use SSE mode](#mcp-sse-mode).

### Use Stdio mode {#mcp-stdio-mode}

1. Add an **MCP Tools** component to your flow.

2. In the **MCP Server** field, select the server you want to add, or click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server**.

    There are multiple ways to add a new server.

    * In the **JSON** pane, paste the MCP server's JSON configuration file, and then click **Add Server**.
    * In the **STDIO** pane, enter the MCP server's **Name**, **Command**, and any **Arguments** or **Environment Variables** the server uses, and then click **Add Server**.
    For example, to start a [Fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) server, the **Command** is `uvx mcp-server-fetch`.
    * In the **SSE** pane, enter your Langflow MCP server's **Name**, **SSE URL**, and any **Headers** or **Environment Variables** the server uses, and then click **Add Server**.
    The default **SSE URL** is `http://localhost:7860/api/v1/mcp/sse`. For more information, see [Use SSE mode](#mcp-sse-mode).

    `uvx` is included with `uv` in the Langflow package.
    To use `npx` server commands, you must first install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
    For an example of an `npx` MCP server in Langflow, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).

3. To use environment variables in your server command, enter each variable in the **Env** fields as you would define them in a script, such as `VARIABLE=value`.

    :::important
    Langflow passes environment variables from the `.env` file to MCP, but it doesn't pass global variables declared in the Langflow UI.
    To define an MCP server environment variable as a global variable, add it to Langflow's `.env` file at startup.
    For more information, see [global variables](/configuration-global-variables).
    :::

4. In the **Tool** field, select a tool that you want this component to use, or leave the field blank to allow access to all tools provided by the MCP server.

    If you select a specific tool, you might need to configure additional tool-specific fields. For information about tool-specific fields, see your MCP server's documentation.

    At this point, the **MCP Tools** component is serving a tool, but nothing is using the tool. The next steps explain how to make the tool available to an [**Agent** component](/components-agents) so that the agent can use the tool in its responses.

5. In the [component menu](/concepts-components#component-menus), enable **Tool mode** so you can use the component with an agent.

6. Connect the **MCP Tools** component's **Toolset** port to an **Agent** component's **Tools** port.

    If not already present in your flow, make sure you also attach **Chat input** and **Chat output** components to the **Agent** component.

    ![MCP tools component in stdio mode](/img/component-mcp-stdio.png)

7.  Test your flow to make sure the MCP server is connected and the selected tool is used by the agent: Click **Playground**, and then enter a prompt that uses the tool you connected through the **MCP Tools** component.
For example, if you use `mcp-server-fetch` with the `fetch` tool, you could ask the agent to summarize recent tech news. The agent calls the MCP server function `fetch`, and then returns the response.

8. If you want the agent to be able to use more tools, repeat these steps to add more **Tools** components with different servers or tools.

### Use SSE mode {#mcp-sse-mode}

Every Langflow project runs a separate MCP server that exposes the project's flows as MCP tools.
For more information about your projects' MCP servers, including how to manage exposed flows, see [Use Langflow as an MCP server](/mcp-server).

To leverage flows-as-tools, use the **MCP Tools** component in **Server-Sent Events (SSE)** mode to connect to a project's `/api/v1/mcp/sse` endpoint:

1. Add an **MCP Tools** component to your flow, click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server**, and then select **SSE** mode.
2. In the **MCP SSE URL** field, modify the default address to point at your Langflow server's SSE endpoint. The default value for other Langflow installations is `http://localhost:7860/api/v1/mcp/sse`.
In SSE mode, all flows available from the targeted server are treated as tools.
3. In the [component menu](/concepts-components#component-menus), enable **Tool mode** so you can use the component with an agent.
4. Connect the **MCP Tools** component's **Toolset** port to an **Agent** component's **Tools** port. If not already present in your flow, make sure you also attach **Chat input** and **Chat output** components to the **Agent** component.
![MCP component with SSE mode enabled](/img/component-mcp-sse-mode.png)
5. Test your flow to make sure the agent uses your flows to respond to queries: Click **Playground**, and then enter a prompt that uses a flow that you connected through the **MCP Tools** component.
6. If you want the agent to be able to use more flows, repeat these steps to add more **MCP Tools** components with different servers or tools selected.

## MCP tools component parameters

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| command | String | Stdio mode only. The MCP server startup command. Default: `uvx mcp-sse-shim@latest`. |
| sse_url | String | SSE mode only. The SSE URL for a Langflow project's MCP server. Default for Langflow Desktop: `http://localhost:7868/`. Default for other installations: `http://localhost:7860/api/v1/mcp/sse` |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| tools | List[Tool] | A list of tools exposed by the MCP server. |

## Manage connected MCP servers

The **Settings > MCP Servers** page manages the MCP servers connected to the Langflow client.

To add a new MCP server, click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server** to open the configuration pane, and follow the steps in [Use the MCP Tools component](#use-the-mcp-tools-component).

Click <Icon name="Ellipsis" aria-hidden="true"/> **More** to configure or delete the MCP server.

## See also

- [Use Langflow as an MCP server](/mcp-server)
- [Use a DataStax Astra DB MCP server with the MCP tools component](/mcp-component-astra)