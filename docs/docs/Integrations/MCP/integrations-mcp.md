---
title: Integrate Langflow with MCP
slug: /integrations-mcp
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction). This allows you to use your Langflow flows as tools in client applications that support the MCP, or extend Langflow with the [MCP server component](/components-tools#mcp-tools-stdio) to access MCP servers.

You can use Langflow as an MCP server with any [MCP client](https://modelcontextprotocol.io/clients).

For configuring interactions between Langflow flows and MCP tools, see [Name and describe your flows for agentic use](#name-and-describe-your-flows-for-agentic-use).

To connect [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) to Langflow for testing and debugging flows, see [Install MCP Inspector to test and debug flows](#install-mcp-inspector-to-test-and-debug-flows).

## Access all of your flows as tools

:::important
Tool names must contain only letters, numbers, underscores, and dashes.
Tool names cannot contain spaces.
To re-name flows in the Langflow UI, click **Flow Name** > **Edit Details**.
:::

Connect an MCP client to Langflow to use your flows as tools.

1. Install [Cursor](https://docs.cursor.com/) or [Claude for Desktop](https://claude.ai/download).
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) to run `uvx` commands. `uvx` is included with `uv` in the Langflow package.
3. Optional: Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) to run `npx` commands.
For an example `npx` server, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).
4. Create at least one flow, and note your host. For example, `http://127.0.0.1:7860`.

<Tabs>
<TabItem value="cursor" label="Cursor">

In Cursor, you can configure a Langflow server in the same way as other MCP servers.
For more information, see the [Cursor MCP documentation](https://docs.cursor.com/context/model-context-protocol).

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

## Name and describe your flows for agentic use

MCP clients like Claude for Desktop and Cursor "see" Langflow as a single MCP server, with **all** of your flows listed as tools.

This can confuse agents, who don't know that flow `adbbf8c7-0a34-493b-90ea-5e8b42f78b66` is a Document Q&A flow for a specific text file.
To prevent this behavior, name and describe your flows clearly for agentic use. Imagine your names and descriptions as function names and code comments, with a clear statement of what problem they solve.

For example, you have created a [Document Q&A](/document-qa) flow that loads a sample resume for an LLM to chat with, and you want Cursor to use the tool.

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

## Install MCP Inspector to test and debug flows

[MCP inspector](https://modelcontextprotocol.io/docs/tools/inspector) is the standard tool for testing and debugging MCP servers.

Use MCP Inspector to monitor your Langflow server's flows, and understand how they are being consumed by the MCP.

To install and run MCP inspector, follow these steps:

1. Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
2. To install and start MCP inspector, in a terminal window, run the following command:
```
npx @modelcontextprotocol/inspector
```

MCP inspector starts by default at `http://localhost:5173`.

:::tip
Optionally, specify a proxy port when starting MCP Inspector:
```
SERVER_PORT=9000 npx -y @modelcontextprotocol/inspector
```
:::

3. In the browser, navigate to MCP Inspector.
4. To inspect the Langflow server, enter the values for the Langflow server.

* In the **Transport Type** field, select **SSE**.
* In the **URL** field, enter the Langflow server's `/mcp/sse` endpoint.
For a default deployment, the URL is `http://127.0.0.1:7860/api/v1/mcp/sse`.

5. Click **Connect**.
MCP Inspector connects to the Langflow server.
6. To confirm the connection, click the **Tools** tab.
The Langflow server's flows are listed as tools, which confirms MCP Inspector is connected.
In the **Tools** tab, you can monitor how your flows are being registered as tools by MCP, and run flows with input values.

To quit MCP Inspector, in the terminal where it's running, enter `Ctrl+C`.