---
title: Integrate Langflow with MCP (Model context protocol)
slug: /integrations-mcp
---

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction). This allows you to use your Langflow flows as tools in other applications that support the MCP protocol, or extend Langflow with the [MCP stdio component](/components-tools#mcp-tools-stdio) to access MCP servers.

* Access all of your flows as tools from Claude Desktop
* Connect a [Datastax Astra DB MCP server](https://github.com/datastax/astra-db-mcp) to Langflow

This guide shows you how to use Langflow as an MCP server with Claude Desktop as the client.

## Access all of your flows as tools from Claude Desktop

Add your Langflow MCP server configuration to Claude, so it can access all of your flows as tools with the MCP protocol.

### Prerequisites

* [Claude desktop](https://claude.ai/download) is installed.
* [uv is installed](https://docs.astral.sh/uv/getting-started/installation/) to enable you to run uvx commands.

### Add Langflow as an MCP server to Claude

1. Create at least one flow, and note your host. For example, `http://127.0.0.1:7863`.
2. Open Claude for Desktop, and then go to the program settings.
For example, on the MacOS menu bar, click **Claude**, and then select **Settings**.
3. In the **Settings** dialog, click **Developer**, and then click **Edit Config**.
This creates a `claude_desktop_config.json` file if you don't already have one.
4. Add the following code to `claude_desktop_config.json`.
Your args may differ for your `uvx` and `Python` installations.

```json
{
 "mcpServers": {
     "langflow": {
         "command": "/bin/sh",
         "args": ["-c", "/opt/homebrew/bin/uvx --python /usr/bin/python3 mcp-sse-shim@latest"],
         "env": {
             "MCP_HOST": "http://127.0.0.1:7864",
             "DEBUG": "true"
         }
     }
  }
}
```

This code adds a new MCP server called `langflow` and starts the [mcp-sse-shim](https://github.com/phact/mcp-sse-shim) package using the specified Python interpreter and uvx.

4. Restart Claude.
Your new tools are available in your chat window. Click the tools icon to see a list of your flows.

You can now use your flows as tools in Claude Desktop.

## Connect an Astra DB MCP server to Langflow

Use the Astra DB MCP server to connect to Astra DB from Langflow.

### Prerequisites

* [An OpenAI API key](https://platform.openai.com/)
* [An Astra DB vector database](https://docs.datastax.com/en/astra-db-serverless/get-started/quickstart.html) with an **Astra DB API endpoint** and **Astra DB application token**

### Add an Astra DB MCP server to Langflow

1. Add your **Astra DB application token** and **Astra API endpoint** to Langflow as [global variables](/configuration-global-variables).
2. Create a [Simple agent starter project](/starter-projects-simple-agent).
3. Remove the **URL** tool and replace it with an **MCP stdio** component.
The flow should look like this:
![MCP stdio component](/img/mcp-stdio-component.png)
4. In the **MCP stdio** component, in the **MCP command** field, add the following code to the **MCP stdio** component.
`npx -y @datastax/astra-db-mcp`.
5. In the **Agent** component, add your **OpenAI API key**.
6. Open the **Playground**.
Since your Langflow is now connected to Astra DB through the MCP protocol, you can use it to create, read, update, and delete data from Astra DB.
