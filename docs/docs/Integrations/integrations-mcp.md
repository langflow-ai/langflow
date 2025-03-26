---
title: Integrate Langflow with MCP (Model context protocol)
slug: /integrations-mcp
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction). This allows you to use your Langflow flows as tools in other applications that support the MCP, or extend Langflow with the [MCP stdio component](/components-tools#mcp-tools-stdio) to access MCP servers.

You can use Langflow as an MCP server with any [MCP client](https://modelcontextprotocol.io/clients).
For example purposes, this guide presents two ways to interact with the MCP:

* [Access all of your flows as tools](#access-all-of-your-flows-as-tools)
* [Use the MCP stdio component to connect Langflow to a Datastax Astra DB MCP server](#connect-an-astra-db-mcp-server-to-langflow)

## Access all of your flows as tools

:::important
Tool names must only contain letters, numbers, underscores, dashes, and cannot contain spaces.
:::

<Tabs>
<TabItem value="cursor" label="Cursor">


In Cursor, you can configure a Langflow server in the same way as other MCP servers. For more information, see the [Cursor MCP documentation](https://docs.cursor.com/context/model-context-protocol).

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
6. You can now use your flows as tools in Cursor.
Cursor determines when to use tools based on your queries, and will request permissions when necessary.

</TabItem>

<TabItem value="claude for desktop" label="Claude for Desktop">


1. Install [Claude for Desktop](https://claude.ai/download).
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) so that you can run `uvx` commands.
3. Create at least one flow, and note your host. For example, `http://127.0.0.1:7860`.
4. Open Claude for Desktop, and then go to the program settings.
For example, on the MacOS menu bar, click **Claude**, and then select **Settings**.
5. In the **Settings** dialog, click **Developer**, and then click **Edit Config**.
This creates a `claude_desktop_config.json` file if you don't already have one.
6. Add the following code to `claude_desktop_config.json`.
Your args may differ for your `uvx` and `Python` installations. To find the correct paths:

   * For `uvx`: Run `which uvx` in your terminal
   * For Python: Run `which python` in your terminal

Replace `PATH/TO/PYTHON` with the Python path from your system.
This command assumes the default Langflow server address of `http://127.0.0.1:7860`.

```json
{
 "mcpServers": {
     "langflow": {
         "command": "/bin/sh",
         "args": ["-c", "uvx --python PATH/TO/PYTHON mcp-sse-shim@latest"],
         "env": {
             "MCP_HOST": "http://127.0.0.1:7860",
             "DEBUG": "true"
         }
     }
  }
}
```

This code adds a new MCP server called `langflow` and starts the [mcp-sse-shim](https://github.com/phact/mcp-sse-shim) package using the specified Python interpreter and uvx.

7. Restart Claude for Desktop.
Your new tools are available in your chat window. Click the tools icon to see a list of your flows.

You can now use your flows as tools in Claude for Desktop.

Claude determines when to use tools based on your queries, and will request permissions when necessary.


</TabItem>
</Tabs>

## Name and describe your flows for agentic use

MCP clients like Claude for Desktop and Cursor "see" Langflow as a single MCP server, with **all** of your flows listed as tools.

This can confuse agents, who don't know that flow `adbbf8c7-0a34-493b-90ea-5e8b42f78b66` is a Document Q&A flow for a specific text file.
To prevent this behavior, name and describe your flows clearly for agentic use. Imagine your names and descriptions as function names and code comments, with a clear statement of what problem they solve.

For example, you have created a [Document Q&A](/tutorials-document-qa) flow which loads a sample resume for an LLM to chat with, and you want Cursor to use the tool.

1. Click **Flow name**, and then select **Edit Details**.
2. The **Name** field should make it clear what the flow does, both to a user and to the agent. For example, name it `Document QA for Resume`.
3. The **Description** field should include a description of what the flow does. For example, describe the flow as `OpenAI LLM Chat with Alex's resume.`
The **Endpoint Name** field does not affect the agent's behavior.
4. To see how an MCP client understands your flow, in Cursor, examine the **MCP Servers**.
The tool is listed as:
```text
document_qa_for_resume
e967f47d-6783-4bab-b1ea-0aaa554194a3: OpenAI LLM Chat with Alex's resume.
```
Your flow name and description provided the agent with a clear purpose for the tool.

5. Ask Cursor a question specifically about the resume, such as `What job experience does Alex have?`
```text
I'll help you explore a resume using the Document QA for Resume flow, which is specifically designed for analyzing resumes.
Let me call this tool.
```
6. Click **Run tool** to continue. The agent requests permissions when necessary.
```
Based on the resume, here's a comprehensive breakdown of the experience:
```
7. Ask about a different resume.
You've provided enough information in the description for the agent to make the correct decision:
```text
I notice you're asking about Emily's job experience.
Based on the available tools, I can see there is a Document QA for Resume flow that's designed for analyzing resumes.
However, the description mentions it's for "Alex's resume" not Emily's. I don't have access to Emily's resume or job experience information.
```

## Connect an Astra DB MCP server to Langflow

Use the [MCP server component](/components-tools#mcp-server) to connect Langflow to a [Datastax Astra DB MCP server](https://github.com/datastax/astra-db-mcp).

1. Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
2. Create an [OpenAI](https://platform.openai.com/) API key.
3. Create an [Astra DB Serverless (Vector) database](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html#create-vector-database), if you don't already have one.
4. Get your database's **Astra DB API endpoint** and an **Astra DB application token** with the Database Administrator role. For more information, see [Generate an application token for a database](https://docs.datastax.com/en/astra-db-serverless/administration/manage-application-tokens.html#database-token).
5. Create a [Simple agent starter project](/starter-projects-simple-agent).
6. Remove the **URL** tool and replace it with an [MCP server component](/components-tools#mcp-server) component.
The flow should look like this:
![MCP stdio component](/img/mcp-server-component.png)
7. In the **MCP server** component, in the **MCP command** field, add the following code.
Replace the values for `ASTRA_TOKEN` and `ASTRA_ENDPOINT` with the values from your Astra database.

```plain
env ASTRA_DB_APPLICATION_TOKEN=ASTRA_TOKEN ASTRA_DB_API_ENDPOINT=ASTRA_ENDPOINT npx -y @datastax/astra-db-mcpnpx -y @datastax/astra-db-mcp
```

:::important
Langflow passes environment variables from the `.env` file to MCP, but not global variables declared in the UI.
To add the values for `ASTRA_DB_APPLICATION_TOKEN` and `ASTRA_DB_API_ENDPOINT` as global variables, add them to Langflow's `.env` file at startup.
For more information, see [global variables](/configuration-global-variables).
:::

8. In the **Agent** component, add your **OpenAI API key**.
9. Open the **Playground**, and then ask the agent, `What collections are available?`

Since Langflow is connected to your Astra DB database through the MCP, the agent chooses the correct tool and connects to your database to retrieve the answer.
```text
The available collections in your database are:
collection_002
hardware_requirements
load_collection
nvidia_collection
software_requirements
```

## Debug flows with the MCP inspector

[MCP inspector](https://modelcontextprotocol.io/docs/tools/inspector) is the standard tool for testing and debugging MCP servers.

To install MCP inspector:

```npx -y 