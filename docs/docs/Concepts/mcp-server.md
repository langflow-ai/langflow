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

* A [Langflow project](/concepts-flows#projects) with at least one flow.

* Any LTS version of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) installed on your computer to use MCP Inspector to [test and debug flows](#test-and-debug-flows).

* [ngrok installed](https://ngrok.com/docs/getting-started/#1-install-ngrok) and an [ngrok authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) if you want to [deploy a public Langflow server](/deployment-public-server).

## Select and configure flows to expose as MCP tools {#select-flows-to-serve}

Each [Langflow project](/concepts-flows#projects) has an MCP server that exposes the project's flows as tools that MCP clients can use to generate responses.

By default, all flows in a project are exposed as tools on the project's MCP server.

The following steps explain how to limit the exposed flows and, optionally, rename flows for agentic use:

1. From the Langflow dashboard, select the project that contains the flows you want to serve as tools, and then click the **MCP Server** tab.
Alternatively, you can quickly access the **MCP Server** tab from within any flow by selecting **Share > MCP Server**.

    The **Auto install** and **JSON** tabs display options for connecting MCP clients to the the project's MCP server.

    The **Flows/Tools** section lists the flows that are currently being served as tools.

    ![MCP server projects page](/img/mcp-server.png)

2. Click <Icon name="Settings2" aria-hidden="true"/> **Edit Tools**.

3. In the **MCP Server Tools** window, select the flows that you want exposed as tools.

    ![MCP server tools](/img/mcp-server-tools.png)

4. Recommended: Edit the **Tool Name** and **Tool Description** to help MCP clients determine which actions your flows provide and when to use those actions:

    - **Tool Name**: Enter a name that makes it clear what the flow does when used as a tool by an agent.

    - **Tool Description**: Enter a description that accurately describes the specific actions the flow performs.

    <details>
    <summary>Name and describe your flows for agentic use</summary>

    MCP clients use the **Tool Name** and **Tool Description** to determine which action to use.

    MCP clients like [Cursor](https://www.cursor.com/) treat your Langflow project as a single MCP server with all of your enabled flows listed as tools.

    This can confuse agents if the flows have unclear names or descriptions.
    For example, a flow's default name is the flow ID, such as `adbbf8c7-0a34-493b-90ea-5e8b42f78b66`.
    This provides no information to an agent about the type of flow or it's purpose.

    To provide more context about your flows, make sure to name and describe your flows clearly when configuring your Langflow project's MCP server.

    It's helpful to think of the names and descriptions as function names and code comments, using clear statements describing the problems your flows solve.

    For example, assume you have a [Document Q&A flow](/document-qa) that uses an LLM to chat about resumes, and you give the flow the following name and description:

    - **Tool Name**: `document_qa_for_resume`

    - **Tool Description**: `A flow for analyzing Emily's resume.`

    After connecting your Langflow MCP server to Cursor, you can ask Cursor about the resume, such as `What job experience does Emily have?`.
    Using the context provided by your tool name and description, the agent can decide to use the `document_qa_for_resume` MCP tool to create a response about Emily's resume.
    If necessary, the agent asks permission to use the flow tool before generating the response.

    If you ask about a different resume, such as `What job experience does Alex have?`, the agent can decide that `document_qa_for_resume` isn't relevant to this request, because the tool description specifies that the flow is for Emily's resume.
    In this case, the agent might use another available tool, or it can inform you that it doesn't have access to information about Alex's.
    For example:

    ```
    I notice you're asking about Alex's job experience.
    Based on the available tools, I can see there is a Document QA for Resume flow that's designed for analyzing resumes.
    However, the description mentions it's for "Emily's resume" not Alex's. I don't have access to Alex's resume or job experience information.
    ```
    </details>

5. Close the **MCP Server Tools** window to save your changes.

{/* The anchor on this section (connect-clients-to-use-the-servers-actions) is currently a link target in the Langflow UI. Do not change. */}
## Connect clients to Langflow's MCP server {#connect-clients-to-use-the-servers-actions}

The following procedure describes how to connect [Cursor](https://www.cursor.com/) to your Langflow project's MCP server to consume your flows as tools.
However, you can connect any [MCP-compatible client](https://modelcontextprotocol.io/clients) following similar steps.

<Tabs>
  <TabItem value="Auto install" label="Auto install" default>

1. Install [Cursor](https://docs.cursor.com/get-started/installation).
2. In the Langflow dashboard, select the project that contains the flows you want to serve, and then click the **MCP Server** tab.
3. To auto install your current Langflow project as an MCP server, click <Icon name="Plus" aria-hidden="True"/> **Add**.
    The installation adds the server's configuration file to Cursor's `mcp.json` configuration file.

    :::important
    Auto installation only works if your HTTP client and Langflow server are on the same local machine.
    In this is not the case, configure the client with the code in the **JSON** tab.
    :::
  </TabItem>
  <TabItem value="JSON" label="JSON">

1. Install [Cursor](https://docs.cursor.com/get-started/installation).
2. In Cursor, go to **Cursor Settings > MCP**, and then click **Add New Global MCP Server**.
This opens Cursor's global MCP configuration file, `mcp.json`.
3. In the Langflow dashboard, select the project that contains the flows you want to serve, and then click the **MCP Server** tab.
4. Copy the code template from the **JSON** tab, and then paste it into `mcp.json` in Cursor.
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

  </TabItem>
</Tabs>

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