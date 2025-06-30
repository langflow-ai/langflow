---
title:  Use Langflow as an MCP client
slug: /mcp-client
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) as both an MCP server and an MCP client.

This page describes how to use Langflow as an MCP client with the **MCP connection** component.

For information about using Langflow as an MCP server, see [Use Langflow as an MCP server](/mcp-server).

## Use the MCP connection component

The **MCP connection** component connects to a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server and exposes the MCP server's tools as tools for [Langflow agents](/agents).

This component has two modes, depending on the type of server you want to access:

* To access tools provided by external, non-Langflow MCP servers, [use Stdio mode](#mcp-stdio-mode).
* To use flows from your [Langflow projects](/concepts-overview#projects) as MCP tools, [use SSE mode](#mcp-sse-mode).

### Use Stdio mode {#mcp-stdio-mode}

1. Add an **MCP connection** component to your flow.

2. In the **MCP Command** field, enter the command to start the MCP server. For example, to start a [Fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) server, the command is `uvx mcp-server-fetch`.

    `uvx` is included with `uv` in the Langflow package.
    To use `npx` server commands, you must first install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
    For an example of an `npx` MCP server in Langflow, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).

3. To use environment variables in your server command, enter each variable in the **Env** fields as you would define them in a script, such as `VARIABLE=value`. If the **Env** field isn't shown, enable it in the component's **Controls** in the [component menu](/concepts-components#component-menu).

    :::important
    Langflow passes environment variables from the `.env` file to MCP, but it doesn't pass  global variables declared in the Langflow UI.
    To define an MCP server environment variable as a global variable, add it to Langflow's `.env` file at startup.
    For more information, see [global variables](/configuration-global-variables).
    :::

1. Click <Icon name="RefreshCw" aria-hidden="true"/> **Refresh** to test the command and retrieve the list of tools provided by the MCP server.

    If you select a specific tool, you might need to configure additional tool-specific fields. For information about tool-specific fields, see your MCP server's documentation.

    At this point, the **MCP connection** component is serving a tool, but nothing is using the tool. The next steps explain how to make the tool available to an [**Agent** component](/components-agents) so that the agent can use the tool in its responses.

6. In the [component menu](/concepts-components#component-menu), enable **Tool mode** so you can use the component with an agent.

7. Connect the **MCP connection** component's **Toolset** port to an **Agent** component's **Tools** port.

    If not already present in your flow, make sure you also attach **Chat input** and **Chat output** components to the **Agent** component.

    ![MCP connection component](/img/component-mcp-stdio.png)

8.  Test your flow to make sure the MCP server is connected and the selected tool is used by the agent: Click **Playground**, and then enter a prompt that uses the tool you connected through the **MCP connection** component.
For example, if you use `mcp-server-fetch` with the `fetch` tool, you could ask the agent to summarize recent tech news. The agent calls the MCP server function `fetch`, and then returns the response.

1. If you want the agent to be able to use more tools, repeat these steps to add more **MCP connection** components with different servers or tools.

### Use SSE mode {#mcp-sse-mode}

Every Langflow project runs a separate MCP server that exposes the project's flows as MCP tools.
For more information about your projects' MCP servers, including how to manage exposed flows, see [Use Langflow as an MCP server](/mcp-server).

To leverage flows-as-tools, use the **MCP connection** component in **Server-Sent Events (SSE)** mode to connect to a project's `/api/v1/mcp/sse` endpoint:

1. Add an **MCP connection** component to your flow, and then select **SSE** mode.
A default address appears in the **MCP SSE URL** field.
1. In the **MCP SSE URL** field, modify the default address to point at your Langflow server's SSE endpoint. The default value for Langflow Desktop is `http://localhost:7868/`. The default value for other Langflow installations is `http://localhost:7860/api/v1/mcp/sse`.
1. Click <Icon name="RefreshCw" aria-label="Refresh"/> to test the endpoint and refresh the **Tools** list.
In SSE mode, all flows available from the targeted server are treated as tools.
1. In the **Tool** field, select a flow that you want this component to use, or leave the field blank to allow access to all flows available from the targeted Langflow server.
2. In the [component menu](/concepts-components#component-menu), enable **Tool mode** so you can use the component with an agent.
3. Connect the **MCP connection** component's **Toolset** port to an **Agent** component's **Tools** port. If not already present in your flow, make sure you also attach **Chat input** and **Chat output** components to the **Agent** component.
![MCP component with SSE mode enabled](/img/component-mcp-sse-mode.png)
1. Test your flow to make sure the agent uses your flows to respond to queries: Click **Playground**, and then enter a prompt that uses a flow that you connected through the **MCP connection** component.
2. If you want the agent to be able to use more flows, repeat these steps to add more **MCP connection** components with different servers or tools selected.

## MCP connection component parameters

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| command | String | Stdio mode only. The MCP server startup command. Default: `uvx mcp-sse-shim@latest`. |
| sse_url | String | SSE mode only. The SSE URL for a Langflow project's MCP server. Default for Langflow Desktop: `http://localhost:7868/`. Default for other installations: `http://localhost:7860/api/v1/mcp/sse` |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| tools | List[Tool] | A list of tools exposed by the MCP server. |

## See also

- [Use Langflow as an MCP server](/mcp-server)
- [Use a DataStax Astra DB MCP server with the MCP connection component](/mcp-component-astra)