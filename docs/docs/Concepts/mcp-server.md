---
title: Model Context Protocol (MCP) server
slug: /mcp-server
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) as both an MCP server and an MCP client.

As an MCP server, you can serve your flows as tools to any [MCP client](https://modelcontextprotocol.io/clients).
All flows within a [project](/concepts-overview#projects) are exposed as actions for MCP clients to use as tools.

To use Langflow as an MCP client to access MCP servers, see the [MCP component](/components-tools#mcp-server).

## Prerequisites

* Install [uv](https://docs.astral.sh/uv/getting-started/installation/) to run `uvx` commands. `uvx` is included with `uv` in the Langflow package.
* Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) to run `npx` commands.
For an example `npx` server, see [Connect an Astra DB MCP server to Langflow](/mcp-component-astra).
* Create at least one flow within your Langflow project, and note your host. For example, `http://127.0.0.1:7860`.

## Serve flows as actions from the MCP server

:::important
If you're using **Langflow for Desktop**, the default address is `http://127.0.0.1:7868/`.
:::
Serve a flow as an action from your MCP server, with a clear name and description for MCP clients to use it as a tool.

1. Navigate to the **MCP** page.
The **MCP** page is available at the `/mcp` URL. For example, if you're running Langflow at the default `http://127.0.0.1:7860` address, the **MCP** page is located at `http://127.0.0.1:7860/mcp`.
:::tip
Alternatively, from the **Workspace**, click **Publish**, and then click **MCP Server**.
:::
2. Click the **MCP Server** tab.
The page presents code templates for connecting your server to client applications.
Your available flows are listed as actions.
![MCP server projects page](/img/mcp-server.png)
3. To add Actions to your server and expose them to clients, click **Edit Actions**.
The **MCP Server Actions** pane appears.
![MCP server actions](/img/mcp-server-actions.png)
4. Select the action you want your server to expose as a tool.
This example adds a Document QA flow based on a resume.
:::important
Tool names must contain only letters, numbers, underscores, and dashes.
Tool names cannot contain spaces.
:::
5. To modify your **Flow Name** and **Flow Description**, in the **MCP Server Actions** pane, click the **Flow name** or **Action**.
6. The **Flow Name** field should make it clear what the flow does, both to a user and to the agent. For example, name the action `document_qa_for_resume`.
7. The **Flow Description** field should include a description of what the action does. For example, describe the flow as `OpenAI LLM Chat with Emily's resume.`
8. Optionally, click <Icon name="RefreshCw" aria-label="Refresh"/> to reset the field value to the original name.
:::tip
The **Flow Name** and **Flow Description** fields must contain text.
:::
9. Close the window. You have named and described your flow as an action that your MCP server is exposing.

## Connect clients to use the server's actions

Connect an MCP client to Langflow to use your flows as actions.

This example uses [Cursor](https://docs.cursor.com/), but you can use any [MCP-compatible client](https://modelcontextprotocol.io/clients) to connect to your server.

1. Install [Cursor](https://docs.cursor.com/).
2. Open Cursor, and then go to **Cursor Settings**.
3. Click MCP, and then click **Add New Global MCP Server**.
Cursor's MCP servers are listed as JSON objects in `mcp.json`.
4. To add a Langflow server, copy the code template from the **MCP Server** page in Langflow and paste it into `mcp.json`.
This example assumes the default Langflow server address of `http://127.0.0.1:7860`.
Replace **PROJECT_ID** with your project ID. Copying the command from the **MCP Server** page does this automatically.
```json
{
  "mcpServers": {
    "langflow-my_projects": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://127.0.0.1:7860/api/v1/mcp/project/**PROJECT_ID**/sse"
      ]
    }
  }
}
```
5. Save the `mcp.json` file, and then click the **Reload** icon.
6. Your Langflow server is now available to Cursor as an MCP server, and your project's added flows are registered as tools.
You can now use your flows as tools in Cursor.
Cursor determines when to use tools based on your queries, and requests permissions when necessary.

For more information, see the [Cursor MCP documentation](https://docs.cursor.com/context/model-context-protocol).

### Langflow MCP server authentication and environment variables

If your Langflow server has `LANGFLOW_AUTO_LOGIN` set to `False`, MCP commands require an API key to connect.
The presented code snippets automatically include the `x-api-key` field, but you need to replace the value for **LANGFLOW_API_KEY** with your Langflow API key.
To create a Langflow API key, in the **MCP Server** tab, click **Create API key**. The key is added to your server command.

```json
{
  "mcpServers": {
    "lf-my_projects": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://127.0.0.1:7860/api/v1/mcp/project/e91ef0c4-86bc-4c7a-a916-c09e242065bd/sse",
        "--header",
        "x-api-key:**LANGFLOW_API_KEY**"
      ]
    }
  }
}
```

For more information, see [Authentication](/configuration-api-keys) and [API keys](/configuration-api-keys).

To include environment variables with your MCP server command, include them like this:

```json
{
  "mcpServers": {
    "langflow-my_projects": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://127.0.0.1:7860/api/v1/mcp/project/**PROJECT_ID**/sse"
      ],
      "env": {
        "key": "value"
      }
    }
  }
}
```

## Name and describe your flows for agentic use

MCP clients Cursor "see" your Langflow project as a single MCP server, with **all** of your enabled flows listed as tools.

This can confuse agents, who don't know that flow `adbbf8c7-0a34-493b-90ea-5e8b42f78b66` is a Document Q&A flow for a specific text file.

To prevent this behavior, name and describe your flows clearly for agentic use. Imagine your names and descriptions as function names and code comments, with a clear statement of what problem they solve.

For example, you previously named and described a [Document Q&A](/document-qa) flow that loads a sample resume for an LLM to chat with, and you want Cursor to use the tool.

1. To see how an MCP client understands your flow, in Cursor, examine the **MCP Servers**.
The tool is listed as:
```text
document_qa_for_resume
```
2. Ask Cursor a question specifically about the resume, such as `What job experience does Emily have?`
The agent asks to call the MCP tool `document_qa_for_resume`, because your name and description provided the agent with a clear purpose for the tool.
3. Click **Run tool** to continue. The agent requests permissions when necessary.
```text
{
  "input_value": "What job experience does Emily have?"
}
Result:
What job experience does Emily have?
Emily J. Wilson has the following job experience:
```
4. Ask about a different resume, such as `What job experience does Alex have?`
You've provided enough information in the description for the agent to make the correct decision:
```text
I notice you're asking about Alex's job experience.
Based on the available tools, I can see there is a Document QA for Resume flow that's designed for analyzing resumes.
However, the description mentions it's for "Emily's resume" not Alex's. I don't have access to Alex's resume or job experience information.
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
For a default deployment, the URL is `http://127.0.0.1:7860/api/v1/mcp/project/**PROJECT_ID**/sse`.

5. Click **Connect**.
MCP Inspector connects to the Langflow server.
6. To confirm the connection, click the **Tools** tab.
The Langflow server's flows are listed as tools, which confirms MCP Inspector is connected.
In the **Tools** tab, you can monitor how your flows are being registered as tools by MCP, and run flows with input values.

To quit MCP Inspector, in the terminal where it's running, enter `Ctrl+C`.

## Deploy your server externally

The Langflow MCP server isn't exposed to the public internet.

To expose it, forward traffic with a sharing platform like [Ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).

This example uses Ngrok, but you can use any similar sharing platform.
This example assumes the default Langflow address of `127.0.0.1:7860`.
If you're using **Langflow for Desktop**, the address is `127.0.0.1:7868`.

