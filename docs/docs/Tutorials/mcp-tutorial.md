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

    To improve the response, you can connect MCP servers to your flow that provide specialized tools for the agent to use when generating responses. In the next part of this tutorial, you'll connect an MCP server that provides the agent with real-time weather information so that it can generate a more specific response.

## Add an MCP Tools component

There are many MCP servers available online that offer different tools for different tasks.
To use an MCP server with an MCP client, you have to make the server available to the client.
With all MCP clients, there are several ways to do this:

* Install the server locally.
* Use `uvx` or `npx` to fetch and run a server package.
* Call a server running remotely, like those available on Smithery.

This tutorial demonstrates how to install a weather server locally with `uv pip install`, and how to use `npx` to run the geolocation server package.
Your particular MCP server's requirements may vary.

In Langflow, you use the **MCP Tools** component to connect a specific MCP server to a flow.
You need one **MCP Tools** component for each MCP server that you want your flow to use.

1. For this tutorial, install a [weather MCP server](https://github.com/isdaniel/mcp_weather_server) on your local machine with uv and Python:

    ```shell
    uv pip install mcp_weather_server
    ```

    Make sure you install the server in the same Python environment where Langflow is running:

    * Langflow in a virtual environment: Activate the environment before installing the server.
    * Langflow Docker image: Install the server inside the Docker container.
    * Langflow Desktop or system-wide Langflow OSS: Install the server globally or in the same user environment where you run Langflow.

2. In your **Simple agent** flow, remove the **URL** and **Calculator** tools, and then add the [**MCP Tools**](/mcp-client) component to your workspace.

3. Click the **MCP Tools** component, and then click <Icon name="Plus" aria-hidden="true"/> **Add MCP Server**.

4. In the **Add MCP Server** pane, provide the server startup command and arguments to connect the weather MCP server to your flow. For this tutorial, use either the **JSON** or **STDIO** option.

    Langflow runs the command to launch the server when the agent determines that it needs to use a tool provided by that server.

    Notice that both configurations provide the same information but in different formats.
    This means that if your MCP server repository only provides a JSON file for the server, you can still use those values with the STDIO option.

    <Tabs>
    <TabItem value="JSON" label="JSON" default>

    To provide the MCP server configuration as a JSON object, select **JSON**, and then paste the server configuration into the **JSON** field:

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

    To provide the MCP server configuration in a GUI format, select **STDIO**, and then enter the MCP server configuration values into the given fields:

    - **Name**: `weather`
    - **Command**: `python`
    - **Arguments**:
      - `-m`
      - `mcp_weather_server`

    </TabItem>
    </Tabs>

5. Click **Add Server**, and then wait for the **Actions** list to populate. This means that the MCP server successfully connected.

    With this weather server, the **MCP Tools** component also adds an optional **City** field.
    For this tutorial, don't enter anything in this field.
    Instead, you will add a geolocation MCP server in the next step, which the agent will use to detect your location.

6. Click the **MCP Tools** component, enable **Tool Mode** in the component's header menu, and then connect the component's **Toolset** port to the **Agent** component's **Tools** port.

    At this point your flow has four connected components:

    * The **Chat Input** component is connected to the **Agent** component's **Input** port. This allows to flow to be triggered by an incoming prompt from a user or application.
    * The **MCP Tools** component with the weather MCP server is connected to the **Agent** component's **Tools** port. The agent may not use this server for every request; the agent only uses this connection if it decides the server can help respond to the prompt.
    * The **Agent** component's **Output** port is connected to the **Chat Output** component, which returns the final response to the user or application.

    ![An agent component connected to an MCP weather server](/img/tutorial-mcp-weather.png)

7. To test the weather MCP server, click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM `Is it safe to go hiking in the Adirondacks today?`

    The  **Playground** shows you the agent's logic as it analyzes the request and select tools to use.

    Ideally, the agent's response will be more specific than the previous response because of the additional context provided by the weather MCP server.
    For example:

    ```
    The current weather in Lake Placid, a central location in the Adirondacks,
    is foggy with a temperature of 17.2°C (about 63°F).
    If you plan to go hiking today, be cautious as fog can reduce visibility
    on trails and make navigation more difficult.
    ```

    This is a better response, but what makes this MCP server more valuable than just calling a weather API?

    First, MCP servers are often customized for specific tasks, such as highly specialized actions or chained tools for complex, multi-step problem solving.
    Typically, you would have to write a custom script for a specific task, possibly including multiple API calls in a single script, and then you would have to either execute this script outside the context of the agent or provide it to your agent in some way.

    Instead, the MCP ensures that all MCP servers are added to agents in the same way, without having to know each server's specific endpoint structures or write custom integrations.
    The MCP is a standardized way to integrate many diverse tools into agentic applications.
    You don't have to learn a new API or write custom code every time you want to use a new MCP server.

    Additionally, you can attach many MCP servers to one agent, depending on the problems you want your application to solve.
    The more servers you add, the more specialized context the agent can use in its responses.
    In this tutorial, adding the weather MCP server already improved the quality of the LLM's response.
    In the next section of the tutorial, you will add a `ip_geolocation` MCP server so the agent can detect the user's location if they don't specify a location in their prompt.

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