---
title: Langfuse
slug: /integrations-langfuse
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Integrate Langfuse with Langflow

> **What is Langfuse?** 
> [Langfuse](https://langfuse.com) ([GitHub](https://github.com/langfuse/langfuse)) is an open-source platform for LLM observability. It provides tracing and monitoring capabilities for AI applications, helping developers debug, analyze, and optimize their AI systems. Langfuse integrates with various tools and frameworks such as workflows builders like Langflow.

This guide walks you through how to configure Langflow to collect [tracing](https://langfuse.com/docs/tracing) data about your flow executions and automatically send the data to Langfuse.

<iframe width="760" height="415" src="https://www.youtube.com/embed/SA9gGbzwNGU?si=eDKvdtvhb3fJCSbl" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## Prerequisites

- A project in Langflow with a runnable flow.
- A Langfuse Account: Sign up for [Langfuse Cloud](https://cloud.langfuse.com) or [self-host Langfuse](https://langfuse.com/self-hosting).

## Step 1: Get Langfuse Credentials

1. In Langfuse, go to your project settings, and then create a new set of API keys.

2. Copy the following API key information:

   - Secret Key
   - Public Key
   - Host URL

## Step 2: Set Langfuse Credentials as Environment Variables

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

## Step 3: Start Langflow and run a flow

1. Start Langflow in the same terminal or environment where you set the environment variables:

```bash
uv run langflow run
```

2. In Langflow, open an existing project, and then run a flow.

## Step 4: View Traces Langfuse

Langflow automatically collects and sends tracing data about the flow execution to Langfuse.
You can view the collected data in your Langfuse project dashboard.

![Example trace in Langfuse](https://langfuse.com//images/blog/langflow-langfuse/langflow-example-trace.png)

_[Public example trace in Langfuse](https://cloud.langfuse.com/project/cm0nywmaa005c3ol2msoisiho/traces/f016ae6d-4527-43f5-93ba-9d78388cd3d9?timestamp=2024-11-15T10%3A22%3A56.378Z&observation=c3680212-31f0-46e2-9310-add4352e4cc7)_

## Disable Langfuse Tracing

To disable the Langfuse integration, remove the environment variables you set in the previous steps and restart Langflow.

## Running Langfuse and Langflow with Docker Compose

If you prefer to self-host Langfuse, you can run both services using Docker Compose. By combining the two docker-compose files, you can streamline the networking between them.

```diff
version: "3.5"
 
services:
  # Adapted from https://github.com/logspace-ai/langflow/blob/dev/docker_example/docker-compose.yml
  langflow:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "7860:7860"
    environment:
+     # Tokens are to be created in Langfuse, then copy-pasted here. Then restart docker-compose.
+     - LANGFUSE_SECRET_KEY=sk-lf-...
+     - LANGFUSE_PUBLIC_KEY=pk-lf-...
+     - LANGFUSE_HOST="http://langfuse-server:3000"
    command: langflow run --host 0.0.0.0
 
  # https://github.com/langfuse/langfuse/blob/main/docker-compose.yml
  langfuse-server:
    image: ghcr.io/langfuse/langfuse:latest
    depends_on:
      - db
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/postgres
      - NEXTAUTH_SECRET=mysecret
      - SALT=mysalt
      - NEXTAUTH_URL=http:localhost:3000
 
  db:
    image: postgres
    restart: always
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=postgres
    ports:
      - 5432:5432
    volumes:
      - database_data:/var/lib/postgresql/data
 
volumes:
  database_data:
    driver: local
```

To test the connectivity between Langflow and Langfuse, run the following command:

```sh
docker compose exec langflow python -c "import requests, os; addr = os.environ.get('LANGFUSE_HOST'); print(addr); res = requests.get(addr, timeout=5); print(res.status_code)"
 
# which should output the following:
# http://langfuse-server:3000
# 200
```
