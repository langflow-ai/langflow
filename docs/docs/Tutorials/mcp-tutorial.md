---
title: Connect to MCP servers from your application
slug: /mcp-tutorial
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to connect MCP tools to your applications using Langflow's **MCP Tools** component.

The [Model Context Protocol](https://modelcontextprotocol.io/), or MCP, helps agents integrate with LLMs.
Langflow can be run as an [MCP client](/mcp-client) and [MCP server](/mcp-server).
In this tutorial, you will use Langflow as a client to connect your application to MCP servers.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [A Langflow API key](/configuration-api-keys)
- [An OpenAI API key](https://platform.openai.com/api-keys)

    This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Create
## Create a Python application that connects to Langflow

Create a Python script that connects to Langflow and asks your LLM if it's a good day to surf.

```python
import requests
import os

url = "http://localhost:7860/api/v1/run/b4d22694-54f4-475d-95dc-12333e3922eb"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": "Is it a good day to surf?"
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

    # Print response
    print(response.text)

except requests.exceptions.RequestException as e:
    print(f"Error making API request: {e}")
except ValueError as e:
    print(f"Error parsing response: {e}")
```

This application works, but it's not very contextually aware.
The LLM will most likely express that it needs to know your location, and if you include your location, the results are generic and not up-to-date.


You can add more up-to-date context with MCP.
The MCP Tools component in Langflow connects to an external MCP server, which can expose APIs as tools, such as “get current time” or “fetch stock price”.
This lets your Langflow agent use those tools directly, and improves the content for the LLM.

## Create an agentic flow to connect to MCP servers

## Run your application with improved context
