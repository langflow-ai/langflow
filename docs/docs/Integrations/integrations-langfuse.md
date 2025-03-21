---
title: Langfuse
slug: /integrations-langfuse
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Integrate Langfuse with Langflow

[Langfuse](https://langfuse.com/) is an observability and analytics platform specifically designed for language models and AI applications.

This guide walks you through how to configure Langflow to collect [tracing](https://langfuse.com/docs/tracing) data about your flow executions and automatically send the data to Langfuse.

## Prerequisites

- A project in Langflow with a runnable flow
- A Langfuse Cloud account in any [data region](https://langfuse.com/faq/all/cloud-data-regions)
- A Langfuse organization and project

## Create Langfuse project credentials

1. In Langfuse, go to your project settings, and then create a new set of API keys.

2. Copy the following API key information:

   - Secret Key
   - Public Key
   - Host URL

## Set your Langfuse credentials as environment variables

Set your Langfuse project credentials as environment variables in the same environment where you run Langflow.

You can use any method you prefer to set environment variables.
The following examples show how to set environment variables in a terminal session (Linux or macOS) and in a command prompt session (Windows):

<Tabs>

<TabItem value="linux-macos" label="Linux or macOS" default>
```
export LANGFUSE_SECRET_KEY=SECRET_KEY
export LANGFUSE_PUBLIC_KEY=PUBLIC_KEY
export LANGFUSE_HOST=HOST_URL
```
</TabItem>

<TabItem value="windows" label="Windows" default>
```
set LANGFUSE_SECRET_KEY=SECRET_KEY
set LANGFUSE_PUBLIC_KEY=PUBLIC_KEY
set LANGFUSE_HOST=HOST_URL
```
</TabItem>

</Tabs>

Replace `SECRET_KEY`, `PUBLIC_KEY`, and `HOST_URL` with the API key information you copied from Langfuse.

## Start Langflow and run a flow

1. Start Langflow in the same terminal or environment where you set the environment variables:

```bash
uv run langflow run
```

2. In Langflow, open an existing project, and then run a flow.

## View tracing data in Langfuse

Langflow automatically collects and sends tracing data about the flow execution to Langfuse.
You can view the collected data in your Langfuse project dashboard.

## Disable the Langfuse integration

To disable the Langfuse integration, remove the environment variables you set in the previous steps and restart Langflow.
