---
title: Connect to MCP servers from your application
slug: /mcp-tutorial
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to connect MCP tools to your applications using Langflow's [**MCP Tools**](/mcp-client) component.

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) helps agents integrate with LLMs through _MCP clients_ and _MCP servers_.
Specifically, MCP servers host tools that agents (MCP clients) use to complete specialized tasks.
MCP servers are connected to MCP clients like Cursor.
Then, you interact with the client, and the client uses tools from the connected servers as needed to complete your requests.

You can run Langflow as an MCP client and an MCP server:

* [Use Langflow as an MCP client](/mcp-client): When run as an MCP client, an **Agent** component in a Langflow flow can use connected components as tools to handle requests.
You can use existing components as tools, and you can connect any MCP server to you flow to make that server's tools available to the agent.

* [Use Langflow as an MCP server](/mcp-server): When run as an MCP server, your flows become tools that can be used by an MCP client, which could be an external client or another Langflow flow.

In this tutorial, you will use the Langflow **MCP Tools** component to connect multiple MCP servers to your flow, and then you'll use a Python application to run your flow and chat with the agent programmatically.

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

    This query demonstrates how an LLM, by itself, might not have access to information or functions designed to address specialized queries. In this example, the default OpenAI model provides a vague response, although the agent does know the current date by using its internal `get_current_date` function.

    ```
    Today is July 11, 2025.
    To determine if it's safe to go hiking in the Adirondacks today, you should check the current weather conditions, trail advisories, and any local alerts (such as bear activity or flooding).
    Would you like a detailed weather forecast or information on trail conditions for the Adirondacks today?
    ```

    To improve the response, you can connect MCP servers to your flow, which provide specialized tools to the agent to use when generating responses. In the next part of this tutorial, you'll connect an MCP server that provides the agent with real-time weather information so that it can generate a more specific response.

## Add an MCP Tools component

There are many MCP servers available online that offer different tools for different tasks.
The **MCP Tools** component is required to use a particular MCP server within a flow.
You need one **MCP Tools** component for each MCP server that you want your flow to use.

    :::tip MCP installation methods
    There are multiple ways to install MCP servers, including local installation, using `uvx` or `npx` to fetch and run the server package, or services like Smithery.
    This tutorial demonstrates both local installation with `uv pip install` for the weather server, and using `npx` for the geolocation server.
    Your particular MCP server's requirements may vary.
    :::

1. To install an MCP server locally, do the following:

    This example installs an [MCP weather server](https://github.com/isdaniel/mcp_weather_server) to your local machine with uv and Python.

    Make sure you install the server in the same Python environment where Langflow is running.
    * If you are running Langflow in a virtual environment, activate that environment before installing the server.
    * If you are using Docker, install the package inside the Docker container.
    * If you are running Langflow system-wide, install the package globally or in the same user environment.

    To install the server, run the following command:
    ```shell
    uv pip install mcp_weather_server
    ```

2. Remove the **URL** and **Calculator** tools, and then drag the [**MCP Tools**](/mcp-client) component into your workspace.
3. In the **MCP Tools** component, click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server**.
4. To configure the MCP server, do the following:

    1. In the **Add MCP Server** pane, select either **JSON** or **STDIO** to enter the configuration for starting your server.
    Both options configure an MCP server in Langflow with a command and arguments, which Langflow executes to launch the server process when needed.
    Both options are included here to demonstrate how the STDIO commands can be filled in from the JSON configuration values.

    <Tabs>
    <TabItem value="JSON" label="JSON" default>

    2. Paste the server configuration into the **JSON** field.
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

    2. Enter the values from the configuration JSON manually into the STDIO fields.
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

6. In the **MCP Tools** component, enable **Tool Mode**, and then connect the **Toolset** port to the **Agent** component's **Tools** port.

    At this point your flow has four components.
    The Chat Input is connected to the Agent component's input port.
    The MCP Tools component is connected to the Agent's Tools port.
    Finally, the Agent component's output port is connected to the Chat Output component, which returns the final response to the application.

    ![An agent component connected to an MCP weather server](/img/tutorial-mcp-weather.png)

7. Click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM `Is it safe to go hiking in the Adirondacks today?`

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
    You can add more servers depending on the problems you want your application to solve.
    The MCP protocol ensures they are all added in the same way to the Agent, without having to know how the endpoints are structured or write custom integrations.

    In the next section, add a `ip_geolocation` MCP server so the user can discover the weather without having to fill in their location.
    If the user wants to know the weather elsewhere instead, the Agent understands the difference and dynamically selects the correct MCP server.

## Add a geolocation server

The [Toolkit MCP Server](https://github.com/cyanheads/toolkit-mcp-server) includes multiple MCP servers for network monitoring, including IP geolocation. It isn't extremely precise, but it doesn't require an API key. The tool returns the IP geolocation of the **Langflow server**, so if your server is deployed elsewhere, consider alternative approaches for getting user-specific location data, such as browser geolocation APIs.

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

At this point, you can open the **Playground** and ask about the weather in your current location to test the IP geolocation tool.
However, the IP geolocation MCP server is most useful in an application where you or your users want to ask about the weather from different places around the world, depending on the Langflow server's location.

In the last part of this tutorial, you'll learn how to use the Langflow API to run a flow in a script.

When you use the Langflow API to run a flow, you can change some aspects of the flow without changing your code.
For example, you can add more MCP servers to your flow in Langflow, and then use the same script to run the flow.
You can use the same input or a new input that prompts the agent to use other tools.

1. To construct a Python application to connect to your flow, gather the following information:

    * `LANGFLOW_SERVER_ADDRESS`: Your Langflow server's domain. The default value is `127.0.0.1:7860`. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `FLOW_ID`: Your flow's UUID or custom endpoint name. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `LANGFLOW_API_KEY`: A valid Langflow API key. To create an API key, see [API keys](/configuration-api-keys).

2. Copy the following script into a Python file, and then replace the placeholders with the information you gathered in the previous step.
    This code contains modifications to the `input_value` to ask about the weather in the user's location, and some parsing code to extract just the message from Langflow's response.

    ```python
    import requests
    import os

    url = "LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID"  # The complete API endpoint URL for this flow

    # Request payload configuration
    payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": "What's the weather like where I am right now?"
    }

    # Request headers
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "LANGFLOW_API_KEY"
    }

    try:
        # Send API request
        response = requests.request("POST", url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        # Parse and print only the message text
        data = response.json()
        message = data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
        print(message)

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
    except ValueError as e:
        print(f"Error parsing response: {e}")
    except (KeyError, IndexError) as e:
        print(f"Error extracting message from response: {e}")
    ```

3.  Save and run the script to send the request and test the flow.
    The application identifies your approximate location with `geolocation`, and then retrieves the weather in that location with `weather`.

    <details closed>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    If you are using a VPN or a similar service, the `geolocation` tool might use the simulated location rather than your actual location.

    ```
    The weather in Waynesboro, Pennsylvania, is currently overcast with a temperature of 23.0°C (about 73.4°F).
    If you need more details or have any other questions, feel free to ask!
    ```

    </details>

## Next steps

To continue building on the concepts introduced in this tutorial, see the following:

* [Use Langflow as an MCP client](/mcp-client)
* [Use Langflow Agents](/agents)
* [Use Langflow as an MCP server](/mcp-server)
* [Langflow deployment overview](/deployment-overview)