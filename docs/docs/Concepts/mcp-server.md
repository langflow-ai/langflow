---
title:  Use Langflow as an MCP server
slug: /mcp-server
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Langflow integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) as both an MCP server and an MCP client.

This page describes how to use Langflow as an MCP server.

For information about using Langflow as an MCP client, see [Use Langflow as an MCP client](/mcp-client).

As an MCP server, Langflow exposes your flows as [tools](https://modelcontextprotocol.io/docs/concepts/tools) that [MCP clients](https://modelcontextprotocol.io/clients) can use to take actions.

## Prerequisites

* A Langflow project with at least one flow.

* Any LTS version of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) installed on your computer to use MCP Inspector to [test and debug flows](#test-and-debug-flows).

* [ngrok installed](https://ngrok.com/docs/getting-started/#1-install-ngrok) and an [ngrok authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) if you want to [deploy a public Langflow server](/deployment-public-server).

## Select and configure flows to expose as MCP tools {#select-flows-to-serve}

Langflow runs a separate MCP server for every [project](/concepts-overview#projects).
The MCP server for each project exposes that project's flows as tools.

All of the flows in a project are exposed by default.
To expose only specific flows and optionally rename them for agentic use, follow these steps:

1. From the Langflow dashboard, select the project that contains the flows you want to serve as tools, and then click the **MCP Server** tab.
Alternatively, you can quickly access the **MCP Server** tab from within any flow by selecting **Publish > MCP Server**.

    The **MCP Server** tab displays a code template that you can use to connect MCP clients to the the project's MCP server.

    The **Flows/Actions** section lists the flows that are currently being served as tools.

    ![MCP server projects page](/img/mcp-server.png)

2. Click <Icon name="Settings2" aria-hidden="true"/> **Edit Actions**.

3. In the **MCP Server Actions** window, select the flows that you want exposed as tools.

    ![MCP server actions](/img/mcp-server-actions.png)

4. Optional: Edit the **Flow Name** and **Flow Description**.

    - **Flow Name**: Enter a name thats makes it clear what the flow does.

    - **Flow Description**: Enter a description that accurately describes the specific action(s) the flow performs.

   :::important
   MCP clients use the **Flow Name** and **Flow Description** to determine which action to use.
   For more information about naming and describing your flows, see [Name and describe your flows for agentic use](#name-and-describe-your-flows).
   :::

5. Close the **MCP Server Actions** window to save your changes.

{/* The anchor on this section (connect-clients-to-use-the-servers-actions) is currently a link target in the Langflow UI. Do not change. */}
## Connect clients to Langflow's MCP server {#connect-clients-to-use-the-servers-actions}

The following procedure describes how to connect [Cursor](https://www.cursor.com/) to your Langflow project's MCP server to consume your flows as tools.
However, you can connect any [MCP-compatible client](https://modelcontextprotocol.io/clients) following similar steps.

1. Install [Cursor](https://docs.cursor.com/get-started/installation).

2. In Cursor, go to **Cursor Settings > MCP**, and then click **Add New Global MCP Server**.
This opens Cursor's global MCP configuration file, `mcp.json`.

3. In the Langflow dashboard, select the project that contains the flows you want to serve, and then click the **MCP Server** tab.

4. Copy the code template from the **MCP Server** tab, and then paste it into `mcp.json` in Cursor.
For example:

    ```json
    {
      "mcpServers": {
        "PROJECT_NAME": {
          "command": "uvx",
          "args": [
            "mcp-proxy",
            "http://LANGFLOW_SERVER_ADDRESS/api/v1/mcp/project/PROJECT_ID/sse"
          ]
        }
      }
    }
    ```

    The **MCP Server** tab automatically includes the correct `PROJECT_NAME`, `LANGFLOW_SERVER_ADDRESS`, and `PROJECT_ID` values.
    The default Langflow server address is `http://localhost:7860`.
    If you have [deployed a public Langflow server](/deployment-public-server), the address is automatically included.

    :::important
    If your Langflow server [requires authentication](/configuration-authentication) ([`LANGFLOW_AUTO_LOGIN`](/environment-variables#LANGFLOW_AUTO_LOGIN) is set to `false`), you must include your Langflow API key in the configuration.
    For more information, see [MCP server authentication and environment variables](#authentication).
    :::

5. Save and close the `mcp.json` file in Cursor.
The newly added MCP server will appear in the **MCP Servers** section.

Cursor is now connected to your project's MCP server and your flows are registered as tools.
Cursor determines when to use tools based on your queries, and requests permissions when necessary.

For more information, see the [Cursor's MCP documentation](https://docs.cursor.com/context/model-context-protocol).

### MCP server authentication and environment variables {#authentication}

If your Langflow server [requires authentication](/configuration-authentication) ([`LANGFLOW_AUTO_LOGIN`](/environment-variables#LANGFLOW_AUTO_LOGIN) is set to `false`), then you must supply a [Langflow API key](/configuration-api-keys) in your MCP client configuration.
When this is the case, the code template in your project's **MCP Server** tab automatically includes the `--header` and `x-api-key` arguments:

```json
{
  "mcpServers": {
    "PROJECT_NAME": {
      "command": "uvx",
      "args": [
        "mcp-proxy",
        "--headers",
        "x-api-key",
        "YOUR_API_KEY",
        "http://LANGFLOW_SERVER_ADDRESS/api/v1/mcp/project/PROJECT_ID/sse"
      ]
    }
  }
}
```

Click <Icon name="key" aria-hidden="true"/> **Generate API key** to automatically insert a new Langflow API key into the code template.
Alternatively, you can replace `YOUR_API_KEY` with an existing Langflow API key.

![MCP server tab showing Generate API key button](/img/mcp-server-api-key.png)

To include environment variables with your MCP server command, include them like this:

```json
{
  "mcpServers": {
    "PROJECT_NAME": {
      "command": "uvx",
      "args": [
        "mcp-proxy",
        "http://LANGFLOW_SERVER_ADDRESS/api/v1/mcp/project/PROJECT_ID/sse"
      ],
      "env": {
        "KEY": "VALUE"
      }
    }
  }
}
```

Replace `KEY` and `VALUE` with the environment variable name and value you want to include.

{/* The anchor on this section (deploy-your-server-externally) is currently a link target in the Langflow UI. Do not change. */}
### Deploy your MCP server externally {#deploy-your-server-externally}

To deploy your MCP server externally with ngrok, see [Deploy a public Langflow server](/deployment-public-server).

## Name and describe your flows for agentic use {#name-and-describe-your-flows}

MCP clients like [Cursor](https://www.cursor.com/) "see" your Langflow project as a single MCP server, with _all_ of your enabled flows listed as tools.
This can confuse agents.
For example, an agent won't know that flow `adbbf8c7-0a34-493b-90ea-5e8b42f78b66` is a [Document Q&A](/document-qa) flow for a specific text file.

To prevent this behavior, make sure to [name and describe](#select-flows-to-serve) your flows clearly.
It's helpful to think of the names and descriptions as function names and code comments, making sure to use clear statements describing the problems your flows solve.

For example, let's say you have a [Document Q&A](/document-qa) flow that loads a sample resume for an LLM to chat with, and that you've given it the following name and description:

 - **Flow Name**: `document_qa_for_resume`

 - **Flow Description**: `A flow for analyzing Emily's resume.`

If you ask Cursor a question specifically about the resume, such as `What job experience does Emily have?`, the agent asks to call the MCP tool `document_qa_for_resume`.
That's because your name and description provided the agent with a clear purpose for the tool.

When you run the tool, the agent requests permissions when necessary, and then provides a response.
For example:

```
{
  "input_value": "What job experience does Emily have?"
}
Result:
What job experience does Emily have?
Emily J. Wilson has the following job experience:
```

If you ask about a different resume, such as `What job experience does Alex have?`, you've provided enough information in the description for the agent to make the correct decision:

```
I notice you're asking about Alex's job experience.
Based on the available tools, I can see there is a Document QA for Resume flow that's designed for analyzing resumes.
However, the description mentions it's for "Emily's resume" not Alex's. I don't have access to Alex's resume or job experience information.
```

## Use MCP Inspector to test and debug flows {#test-and-debug-flows}

[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is a common tool for testing and debugging MCP servers.
You can use MCP Inspector to monitor your flows and get insights into how they are being consumed by the MCP server:

1. Install MCP Inspector:

    ```bash
    npx @modelcontextprotocol/inspector
    ```

    For more information about configuring MCP Inspector, including specifying a proxy port, see the [MCP Inspector GitHub project](https://github.com/modelcontextprotocol/inspector).

2. Open a web browser and navigate to the MCP Inspector UI.
The default address is `http://localhost:6274`.

3. In the MCP Inspector UI, enter the connection details for your Langflow project's MCP server:

    - **Transport Type**: Select **SSE**.
    - **URL**: Enter the Langflow MCP server's `sse` endpoint. For example: `http://localhost:7860/api/v1/mcp/project/d359cbd4-6fa2-4002-9d53-fa05c645319c/sse`

    If you've [configured authentication for your MCP server](#authentication), fill out the following additional fields:
    - **Transport Type**: Select **STDIO**.
    - **Command**: `uvx`
    - **Arguments**: Enter the following list of arguments, separated by spaces. Replace the values for `YOUR_API_KEY`, `LANGFLOW_SERVER_ADDRESS`, and `PROJECT_ID` with the values from your Langflow MCP server. For example:
    ```bash
    mcp-proxy --headers x-api-key YOUR_API_KEY http://LANGFLOW_SERVER_ADDRESS/api/v1/mcp/project/PROJECT_ID/sse
    ```

4. Click **Connect**.

    If the connection was successful, you should see your project's flows in the **Tools** tab.
    From this tab, you can monitor how your flows are being registered as tools by MCP, as well as test the tools with custom input values.

5. To quit MCP Inspector, press <kbd>Control+C</kbd> in the same terminal window where you started it.

## Troubleshooting MCP server

If Claude for Desktop is not using your server's tools correctly, you may need to explicitly define the path to your local `uvx` or `npx` executable file in the `claude_desktop_config.json` configuration file.

1. To find your UVX path, run `which uvx`.
To find your NPX path, run `which npx`.

2. Copy the path, and then replace `PATH_TO_UVX` or `PATH_TO_NPX` in your `claude_desktop_config.json` file.

<Tabs>
  <TabItem value="uvx" label="uvx" default>

```json
{
  "mcpServers": {
    "PROJECT_NAME": {
      "command": "PATH_TO_UVX",
      "args": [
        "mcp-proxy",
        "http://LANGFLOW_SERVER_ADDRESS/api/v1/mcp/project/PROJECT_ID/sse"
      ]
    }
  }
}
```
  </TabItem>

  <TabItem value="npx" label="npx">

```json
{
  "mcpServers": {
    "PROJECT_NAME": {
      "command": "PATH_TO_NPX",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://LANGFLOW_SERVER_ADDRESS/api/v1/mcp/project/PROJECT_ID/sse"
      ]
    }
  }
}
```
  </TabItem>
</Tabs>

## See also

- [Use Langflow as an MCP client](/mcp-client)
- [Use a DataStax Astra DB MCP server](/mcp-component-astra)