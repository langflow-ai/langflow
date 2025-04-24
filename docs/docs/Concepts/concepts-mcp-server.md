---
title: MCP server
slug: /concepts-mcp-server
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction). This allows you to use your Langflow flows as tools in client applications that support the MCP, or extend Langflow with the [MCP server component](/components-tools#mcp-tools-stdio) to access MCP servers.

You can use Langflow as an MCP server with any [MCP client](https://modelcontextprotocol.io/clients).
All flows within a [project](/concepts-overview#projects) are exposed as "Actions" for MCP clients to perform.

For configuring interactions between Langflow flows and MCP tools, see [Name and describe your flows for agentic use](#name-and-describe-your-flows-for-agentic-use).

## Access a project's flows as tools

:::important
Tool names must contain only letters, numbers, underscores, and dashes.
Tool names cannot contain spaces.
To re-name flows in the Langflow UI, click **Flow Name** > **Edit Details**.
:::

Connect an MCP client to Langflow to use your flows as tools.

### Prerequisites

* Install [uv](https://docs.astral.sh/uv/getting-started/installation/) to run `uvx` commands. `uvx` is included with `uv` in the Langflow package.
* Optional: Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) to run `npx` commands.
For an example `npx` server, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).
* Create at least one flow within your Langflow project, and note your host. For example, `http://127.0.0.1:7860`.

1. Navigate to the **Projects** page.
The **Projects** page is available at the `/projects` URL. For example, if you're running Langflow at the default `http://127.0.0.1:7860` address, the **Projects** page is located at `http://127.0.0.1:7860/projects`.
2. Click the **MCP Server** tab.
The page presents code templates for connecting your server to client applications.
![MCP server projects page](/img/mcp-server-projects.png)
3. 

<Tabs>
<TabItem value="cursor" label="Cursor">

In Cursor, you can configure a Langflow server in the same way as other MCP servers.
For more information, see the [Cursor MCP documentation](https://docs.cursor.com/context/model-context-protocol).
1. Install [Cursor](https://docs.cursor.com/).
1. Open Cursor, and then go to **Cursor Settings**.
2. Click MCP, and then click **Add New Global MCP Server**.
Cursor's MCP servers are listed as JSON objects.
3. To add a Langflow server, add an entry for your Langflow server's `/v1/mcp/sse` endpoint.
This example assumes the default Langflow server address of `http://127.0.0.1:7860`.
```json
{
  "mcpServers": {
    "langflow": {
      "url": "http://127.0.0.1:7860/api/v1/mcp/sse"
    }
  }
}
```
4. Save the `mcp.json` file, and then click the **Reload** icon.
5. Your Langflow server is now available to Cursor as an MCP server, and all of its flows are registered as tools.
You can now use your flows as tools in Cursor.
Cursor determines when to use tools based on your queries, and requests permissions when necessary.

</TabItem>

<TabItem value="claude for desktop" label="Claude for Desktop">

In Claude for Desktop, you can configure a Langflow server in the same way as other MCP servers.
For more information, see the [Claude for Desktop MCP documentation](https://modelcontextprotocol.io/quickstart/user).
1. Install [Claude for Desktop](https://claude.ai/download).
1. Open Claude for Desktop, and then go to the program settings.
For example, on the MacOS menu bar, click **Claude**, and then select **Settings**.
2. In the **Settings** dialog, click **Developer**, and then click **Edit Config**.
This creates a `claude_desktop_config.json` file if you don't already have one.
3. Add the following code to `claude_desktop_config.json`.

Your `args` may differ for your `uvx` and `Python` installations. To find your system paths, do the following:

4. To find the `uvx` path, run `which uvx` in your terminal. Replace `PATH/TO/UVX` with the `uvx` path from your system.
5. To find the `python` path, run `which python` in your terminal. Replace `PATH/TO/PYTHON` with the Python path from your system.

This command assumes the default Langflow server address of `http://127.0.0.1:7860`.

```json
{
 "mcpServers": {
     "langflow": {
         "command": "/bin/sh",
         "args": ["-c", "PATH/TO/UVX --python PATH/TO/PYTHON mcp-sse-shim@latest"],
         "env": {
             "MCP_HOST": "http://127.0.0.1:7860",
             "DEBUG": "true"
         }
     }
  }
}
```

This code adds a new MCP server called `langflow` and starts the [mcp-sse-shim](https://github.com/phact/mcp-sse-shim) package using the specified Python interpreter and uvx.

6. Restart Claude for Desktop.
Your new tools are available in your chat window, and Langflow is available as an MCP server.

  * To view your tools, click the <Icon name="Hammer" aria-label="Tools" /> icon.
  * To view a list of connected MCP servers, which includes **langflow-mcp-server**, click the <Icon name="Unplug" aria-label="Connector" /> icon.

You can now use your flows as tools in Claude for Desktop.

Claude determines when to use tools based on your queries, and will request permissions when necessary.

For more information, see [Debugging in Claude for Desktop](https://modelcontextprotocol.io/docs/tools/debugging#debugging-in-claude-desktop).

</TabItem>
</Tabs>

## Name and describe the server's actions

1. To name, describe, and enable or disable individual actions in your project, in the **MCP Server** page, click **Edit Actions**.
The **Edit Actions** pane allows you to modify an action's **Name**, **Description**, and **Enabled**.
![MCP server actions](/img/mcp-server-actions.png)

2. Available options are

