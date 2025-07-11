---
title: Connect to MCP servers from your application
slug: /mcp-tutorial
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to connect MCP tools to your applications using Langflow's [**MCP Tools**](/mcp-client) component.

The [Model Context Protocol](https://modelcontextprotocol.io/), or MCP, helps agents integrate with LLMs.
Langflow can be run as an [MCP client](/mcp-client) and [MCP server](/mcp-server).
In this tutorial, you will use Langflow as a client to connect to MCP servers, and then connect a Python application to Langflow.

## Prerequisites

* [A running Langflow instance](/get-started-installation)
* [A Langflow API key](/configuration-api-keys)
* [An OpenAI API key](https://platform.openai.com/api-keys)

This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Create an agentic flow

1. In Langflow, click **New Flow**, and then select the [**Simple agent**](/simple-agent) template.
2. In the **Agent** component, enter your OpenAI API key.
    If you want to use a different provider or model, edit the **Model Provider**, **Model Name**, and **API Key** fields accordingly.
3. To test the flow, click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM `Is it safe to go hiking in the Adirondacks today?`

    The LLM response is vague, though the Agent does know the current date by using its internal `get_current_date` function.

    ```
    Today is July 11, 2025.
    To determine if it's safe to go hiking in the Adirondacks today, you should check the current weather conditions, trail advisories, and any local alerts (such as bear activity or flooding).
    Would you like a detailed weather forecast or information on trail conditions for the Adirondacks today?
    ```

    For improved, up-to-date context for your Agent, replace the connected tools with a connection to a weather MCP server.

## Add an MCP Tools component

    :::tip Manage MCP Servers
    You can manage your MCP servers' configurations in the **Settings** menu, but you still need an **MCP Tools** component in your flow for each individual server.
    :::

1. Remove the **URL** and **Calculator** tools, and then drag the [**MCP Tools**](/mcp-client) component into your workspace.
2. In the **MCP Tools** component, click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server**.

3. There are multiple ways to install MCP servers, which are covered in the [**MCP Tools**](/mcp-client) component page.

    This example installs an [MCP weather server](https://github.com/isdaniel/mcp_weather_server) to your local machine with uv and Python.

    Make sure you install the server in the same Python environment where Langflow is running.
    * If you are running Langflow in a virtual environment, activate that environment before installing the server.
    * If you are using Docker, install the package inside the Docker container.
    * If you are running Langflow system-wide, install the package globally or in the same user environment.

    To install the server, run the following command:
    ```shell
    uv pip install mcp_weather_server
    ```

4. Configure the MCP server.

    In the **Add MCP Server** pane, select either **JSON** or **STDIO** to enter the configuration for starting your server.
    Both options configure an MCP server in Langflow with a command and arguments, which Langflow executes to launch the server process when needed.
    Both are included here to demonstrate how the STDIO commands can be filled in from the JSON configuration values.

    <Tabs>
    <TabItem value="JSON" label="JSON" default>

    Paste the server configuration into the **JSON** field.
    ```json
    {
      "mcpServers": {
        "weather": {
          "command": "python",
          "args": [
            "-m",
            "mcp_weather_server"
          ],
          "disabled": false,
          "autoApprove": []
        }
      }
    }
    ```

    </TabItem>
    <TabItem value="STDIO" label="STDIO">

    Enter the values from the configuration JSON manually into the STDIO fields.
    Some MCP server repositories only offer JSON files, which you can parse out into the STDIO fields.

    - **Name:** `weather`
    - **Command:** `python`
    - **Arguments:**
      - `-m`
      - `mcp_weather_server`

    </TabItem>
    </Tabs>

5. Click **Add Server**.
    When the **Actions** list populates, the MCP server is ready.
    In the **MCP Tools** component, a field for **City** appears, but you don't need to fill in any more specific values.
    Connecting your MCP server to an **Agent** will define those values based on the request.

3. In the **MCP Tools** component, enable **Tool Mode**, and then connect the **Toolset** port to the **Agent** component's **Tools** port.

    At this point your flow has four components.
    The Chat Input is connected to the Agent component's input port.
    The MCP Tools component is connected to the Agent's Tools port.
    Finally, the Agent component's output port is connected to the Chat Output component, which returns the final response to the application.

    ![An agent component connected to an MCP weather server](/img/tutorial-mcp-weather.png)

4. Click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM `Is it safe to go hiking in the Adirondacks today?`

    The Agent's response is more useful than the previous response, because you provided context with the MCP server.

    <details closed>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    ```
    The current weather in Lake Placid, a central location in the Adirondacks,
    is foggy with a temperature of 17.2°C (about 63°F).
    If you plan to go hiking today, be cautious as fog can reduce visibility
    on trails and make navigation more difficult.
    ```

    </details>

    This is improved, but what makes adding MCP servers different from just calling a weather API?

    The `weather` MCP server is just **one** MCP server, and it's already improved your LLM's context.
    You can add more servers depending on the problems you want your application to solve. The MCP protocol ensures they are all added in the same way to the Agent, without having to know how the endpoints are structured or write custom integrations.

    In the next section, add a `ip_geolocation` MCP server so the user can discover the weather without having to fill in their location.
    If the user wants to know the weather elsewhere instead, the Agent understands the difference and dynamically selects the correct MCP server.

## Add a geolocation server

The [Toolkit MCP Server](https://github.com/cyanheads/toolkit-mcp-server) includes multiple MCP servers for network monitoring, including IP geolocation. It isn't extremely precise, but it doesn't require an API key.

This MCP server can be started with [npx](https://docs.npmjs.com/cli/v8/commands/npx), which downloads and runs the [Node registry package](https://www.npmjs.com/package/@cyanheads/toolkit-mcp-server) with one command without installing the package locally.

1. To add the Toolkit MCP Server to your flow, drag another MCP Tools component to your existing flow, and then click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server**.
2. Click **Add Server**.
    In the **STDIO** pane, enter the following:

    - **Name:** `ip_geolocation`
    - **Command:** `npx @cyanheads/toolkit-mcp-server`

    When the **Actions** list populates, the server is ready.

3. In the **MCP Tools** component, enable **Tool Mode**, and then connect the **Toolset** port to the **Agent** component's **Tools** port.

    At this point, the flow has an additional `ip_geolocation` MCP tools component connected to the Agent.

    ![An agent component connected to MCP weather and geolocation servers](/img/tutorial-mcp-geolocation.png)

## Create a Python application that connects to Langflow

At this point, you can open the Playground and ask what the weather is, but an additional feature of using MCP with Langflow is connecting your flows to your code.

This way, you can add MCP servers in the visual builder to improve your application's results, while not changing any code.

1. To construct a Python application to connect to your flow, gather the following information:gather the following information:

    * `LANGFLOW_SERVER_ADDRESS`: Your Langflow server's domain. The default value is `127.0.0.1:7860`. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `FLOW_ID`: Your flow's UUID or custom endpoint name. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `LANGFLOW_API_KEY`: A valid Langflow API key. To create an API key, see [API keys](/configuration-api-keys).

2. Copy the following script into a Python file, and then replace the placeholders with the information you gathered in the previous step.
    This code contains modifications to the `input_value` to ask about the weather in the user's location, and some parsing code to extract just the message from Langflow's response.

    ```python
    import requests
    import os

    url = "http://localhost:7861/api/v1/run/10424198-e0da-44b8-91d1-97d55b0e96ce"  # The complete API endpoint URL for this flow

    # Request payload configuration
    payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": "What's the weather like where I am right now?"
    }

    # Request headers
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "LANGFLOW_API_KEY"  # Authentication key from environment variable
    }

    try:
        # Send API request
        response = requests.request("POST", url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        # Print response
        print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
    except ValueError as e:
        print(f"Error parsing response: {e}")
    ```

3.  Save and run the script to send the request and test the flow.
    Your application correctly identifies your approximate location with `geolocation`, and retrieves the weather in that location with `weather`.

    <details closed>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    ```
    The weather in Waynesboro, Pennsylvania, is currently overcast with a temperature of 23.0°C (about 73.4°F). If you need more details or have any other questions, feel free to ask!
    ```

    </details>

## Next steps

For more information on building or extending this tutorial, see the following:

* [Connect applications to agents](/agent-tutorial)
* [Langflow deployment overview](/deployment-overview)