---
title: MCP (Model context protocol)
slug: /integrations-mcp
---

# Integrate Langflow with MCP

Langflow integrates with the Model Context Protocol (MCP). This allows you to use your Langflow flows as tools in other applications that support the MCP protocol, or extend Langflow with the MCP stdio component to access MCP servers.

* Access all of your flows as tools from Claude Desktop
* Use MCP components as tools that connect to MCP servers outside of Langflow
* Connect Langflow to Astra DB

This guide will show you how to use Langflow as an MCP server with Claude Desktop as the client.

## Access all of your flows as tools from Claude Desktop

The MCP server configuration is added to Claude, which can then access all of your flows as tools with the MCP protocol.

### Prerequisites

* Claude desktop installed
* Langflow installed and running
* uv installed (https://docs.astral.sh/uv/getting-started/installation/) to run uvx commands

### Add Langflow as an MCP server to Claude

1. Create at least one flow, and note your host, for example, `http://127.0.0.1:7863`

2. Open Claude Desktop. Go to **Settings** > **Developer** > **Edit Config**.
This opens `claude_desktop_config.json`, which describes to Claude what MCP servers are available.
3. Add the following code to  `claude_desktop_config.json`.

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

Your args may differ for your uvx and Python installations.

4. Restart Claude.
You should see new tools in your chat window. Click the tools icon to see a list of your flows.

You can now use your flows as tools in your chat.

## Connect an Astra DB MCP server to Langflow

Use the Astra DB MCP server to connect to Astra DB from Langflow.

### Prerequisites

* [An OpenAI API key](https://platform.openai.com/)
* [An Astra DB vector database](https://docs.datastax.com/en/astra-db-serverless/get-started/quickstart.html)
* Astra DB API endpoint and application token

### Add an Astra DB MCP server to Langflow

1. Add your **Astra DB application token** and **API endpoint** to Langflow as environment variables.
2. Create a [](/starter-projects-simple-agent) project.
3. Remove the **URL** tool and replace it with an **MCP stdio** component.
The flow should look like this:
![MCP stdio component](/img/mcp-stdio-component.png)
4. In the **MCP stdio** component, in the **MCP command** field, add the following code to the **MCP stdio** component.
`npx -y @datastax/astra-db-mcp`
5. Open the **Playground**.
Since your Langflow is now connected to Astra DB through the MCP protocol, you can use it to create, read, update, and delete data from Astra DB.

## Connect an Astra DB MCP server to Cursor



