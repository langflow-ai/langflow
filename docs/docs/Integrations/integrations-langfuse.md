---
title: Langfuse
slug: /integrations-langfuse
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Integrate Langfuse with Langflow

[Langfuse](https://langfuse.com) ([GitHub](https://github.com/langfuse/langfuse)) is an open-source platform for LLM observability. It provides tracing and monitoring capabilities for AI applications, helping developers debug, analyze, and optimize their AI systems. Langfuse integrates with various tools and frameworks such as workflows builders like Langflow.

This guide walks you through how to configure Langflow to collect [tracing](https://langfuse.com/docs/tracing) data about your flow executions and automatically send the data to Langfuse.

<iframe width="760" height="415" src="https://www.youtube.com/embed/SA9gGbzwNGU?si=eDKvdtvhb3fJCSbl" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## Prerequisites

- A project in Langflow with a runnable flow
- A [Langfuse Cloud](https://cloud.langfuse.com) or [self-hosted Langfuse](https://langfuse.com/self-hosting) account

## Set Langfuse credentials as environment variables

1. In Langfuse, go to **Project Settings**, and then create a new set of API keys.

2. Copy the following API key information:

  - Secret Key
  - Public Key
  - Host URL

3. Set your Langfuse project credentials as environment variables in the same environment where you run Langflow.

The following examples set environment variables in a Linux or macOS terminal session or in a Windows command prompt session:
Replace `SECRET_KEY`, `PUBLIC_KEY`, and `HOST_URL` with the API key information you copied from Langfuse.
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

## Start Langflow and view traces in Langfuse

1. Start Langflow in the same terminal or environment where you set the environment variables:

```bash
uv run langflow run
```

2. In Langflow, open an existing project, and then run a flow.

    Langflow automatically collects and sends tracing data about the flow execution to Langfuse.

3. View the collected data in your Langfuse project dashboard.

![Example trace in Langfuse](https://langfuse.com//images/blog/langflow-langfuse/langflow-example-trace.png)

For a live public example trace in a Langfuse dashboard, see [Public example trace in Langfuse](https://cloud.langfuse.com/project/cm0nywmaa005c3ol2msoisiho/traces/f016ae6d-4527-43f5-93ba-9d78388cd3d9?timestamp=2024-11-15T10%3A22%3A56.378Z&observation=c3680212-31f0-46e2-9310-add4352e4cc7).

## Disable Langfuse Tracing

To disable the Langfuse integration, remove the environment variables you set in the previous steps and restart Langflow.

## Run Langfuse and Langflow with Docker Compose

If you prefer to self-host Langfuse, you can run both services with Docker Compose.

1. In Langfuse, go to **Project Settings**, and then create a new set of API keys.

2. Copy the following API key information:

  - Secret Key
  - Public Key
  - Host URL

3. Add your Langflow API keys to your `docker-compose.yml` file.
An example [docker-compose.yml](https://github.com/langflow-ai/langflow/blob/main/docker_example/docker-compose.yml) file is available in the Langflow GitHub repo.
```yml
services:
  langflow:
    image: langflowai/langflow:latest # or another version tag on https://hub.docker.com/r/langflowai/langflow
    pull_policy: always               # set to 'always' when using 'latest' image
    ports:
      - "7860:7860"
    depends_on:
      - postgres
    environment:
      - LANGFLOW_DATABASE_URL=postgresql://langflow:langflow@postgres:5432/langflow
      # This variable defines where the logs, file storage, monitor data and secret keys are stored.
      - LANGFLOW_CONFIG_DIR=app/langflow
      - LANGFUSE_SECRET_KEY=sk-...
      - LANGFUSE_PUBLIC_KEY=pk-...
      - LANGFUSE_HOST=https://us.cloud.langfuse.com
    volumes:
      - langflow-data:/app/langflow

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: langflow
      POSTGRES_PASSWORD: langflow
      POSTGRES_DB: langflow
    ports:
      - "5432:5432"
    volumes:
      - langflow-postgres:/var/lib/postgresql/data

volumes:
  langflow-postgres:
  langflow-data:
```

4. Start the Docker container.
```text
docker-compose up
```
5. To confirm Langfuse is connected to your Langflow container, run this command.
Ensure you've exported `LANGFLOW_HOST` as a variable in your terminal.
```sh
docker compose exec langflow python -c "import requests, os; addr = os.environ.get('LANGFUSE_HOST'); print(addr); res = requests.get(addr, timeout=5); print(res.status_code)"
```

An output similar to this indicates success:
```text
https://us.cloud.langfuse.com
200
```