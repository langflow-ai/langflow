---
title: Integrate Langflow with MCP (Model context protocol)
slug: /integrations-mcp
---

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction). This allows you to use your Langflow flows as tools in other applications that support the MCP, or extend Langflow with the [MCP stdio component](/components-tools#mcp-tools-stdio) to access MCP servers.

You can use Langflow as an MCP server with any [MCP client](https://modelcontextprotocol.io/clients).
For example purposes, this guide presents two ways to interact with the MCP:

* Access all of your flows as tools from [Claude desktop](https://claude.ai/download)
* Use the [MCP stdio component](/components-tools#mcp-tools-stdio) to connect Langflow to a [Datastax Astra DB MCP server](https://github.com/datastax/astra-db-mcp)

## Access all of your flows as tools from Claude Desktop


1. Install [Claude Desktop](https://claude.ai/download).
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) so that you can run `uvx` commands.
3. Create at least one flow, and note your host. For example, `http://127.0.0.1:7863`.
2. Open Claude for Desktop, and then go to the program settings.
For example, on the MacOS menu bar, click **Claude**, and then select **Settings**.
3. In the **Settings** dialog, click **Developer**, and then click **Edit Config**.
This creates a `claude_desktop_config.json` file if you don't already have one.
4. Add the following code to `claude_desktop_config.json`.
Your args may differ for your `uvx` and `Python` installations. To find the correct paths:

   * For `uvx`: Run `which uvx` in your terminal
   * For Python: Run `which python` in your terminal

Replace `/path/to/uvx` and `/path/to/python` with the paths from your system:

```json
{
 "mcpServers": {
     "langflow": {
         "command": "/bin/sh",
         "args": ["-c", "/path/to/uvx --python /path/to/python mcp-sse-shim@latest"],
         "env": {
             "MCP_HOST": "http://127.0.0.1:7864",
             "DEBUG": "true"
         }
     }
  }
}
```

This code adds a new MCP server called `langflow` and starts the [mcp-sse-shim](https://github.com/phact/mcp-sse-shim) package using the specified Python interpreter and uvx.

5. Restart Claude Desktop.
Your new tools are available in your chat window. Click the tools icon to see a list of your flows.

You can now use your flows as tools in Claude Desktop.

## Connect an Astra DB MCP server to Langflow


1. Create an [OpenAI](https://platform.openai.com/) API key.
2. Create an [Astra DB Serverless (Vector) database](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html#create-vector-database), if you don't already have one.
3. Get your database's **Astra DB API endpoint** and an **Astra DB application token** with the Database Administrator role. For more information, see [Generate an application token for a database](https://docs.datastax.com/en/astra-db-serverless/administration/manage-application-tokens.html#database-token).
4. Add your **Astra DB application token** and **Astra API endpoint** to Langflow as [global variables](/configuration-global-variables).
2. Create a [Simple agent starter project](/starter-projects-simple-agent).
3. Remove the **URL** tool and replace it with an **MCP stdio** component.
The flow should look like this:
![MCP stdio component](/img/mcp-stdio-component.png)
4. In the **MCP stdio** component, in the **MCP command** field, add the following code:

```plain
npx -y @datastax/astra-db-mcp
```

5. In the **Agent** component, add your **OpenAI API key**.
6. Open the **Playground**.
Langflow is now connected to your Astra DB database through the MCP.
You can use the MCP to create, read, update, and delete data from your database.
