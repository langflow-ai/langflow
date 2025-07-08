---
title: Connect to MCP servers from your application
slug: /mcp-tutorial
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to

For example, you could

The main focus of this tutorial is to

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [A Langflow API key](/configuration-api-keys)
- [An OpenAI API key](https://platform.openai.com/api-keys)

    This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Create an application that connects to Langflow

Create a Python application that reads

```python

```

This application works, but it's not very contextually aware.
You can add more up-to-date context with MCP.
The MCP Tools component in Langflow connects to an MCP server, which can expose one or more APIs/tools, such as “get current time”, “fetch stock price”.
This lets your Langflow agent use those tools dynamically, rather than being limited to a single, hardcoded API.

## Create an agentic flow to connect to MCP servers

## Run your application with improved context
