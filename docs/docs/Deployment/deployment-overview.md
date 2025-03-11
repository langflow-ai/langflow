---
title: Langflow deployment overview
slug: /deployment-overview
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

You have a flow, and want to share it with the world in a production environment.

This page outlines the journey from locally-run flow to a cloud-hosted production server.

More specific instructions can be found in the [Docker](/deployment-docker) and [Kubernetes](/deployment-kubernetes) pages.

## Langflow deployment architecture

// architecture image

Langflow can be deployed as an **IDE** or as a **runtime**.

The **IDE** includes the frontend, for visual development of your flow.

The default https://github.com/langflow-ai/langflow/blob/main/docker_example/docker-compose.yml[docker-compose.yml] file hosted in the Langflow repository builds the Langflow IDE with an additional PostgreSQL service for storage. For more on starting Langflow with Docker, see [Docker](/deployment-docker).

The **runtime** is a headless or backend-only mode. The server exposes your flow as an endpoint, and runs only the backend processes necessary to run your flow, with PostgreSQL as the database. For more on starting this file, see [Docker](/deployment-docker).

## Package your flow with the Langflow runtime image

To package your flow as a Docker image, include the flow's `.JSON` file in the folder you build for locally.

For example, if you have your flow stored in a directory like this:

```plain
./
├── Dockerfile
├── README.md
├── flows/
    └── basic_prompting.json
```

Your Dockerfile would look like this:

```dockerfile
FROM langflowai/langflow:latest
RUN mkdir -p /app/flows
COPY ./flows/*.json /app/flows/
```

The Dockerfile includes the command `COPY ./flows/*.json /app/flows/` which copies all JSON files from your local flows directory into the container's `/app/flows` directory. This makes your flow definitions available to the Langflow runtime when the container starts.

An example https://github.com/langflow-ai/langflow-helm-charts/blob/main/examples/langflow-runtime/docker/Dockerfile[Dockerfile] for bundling flows is hosted in the Langflow Helm Charts repository.

Build the Docker image

For more on building the Langflow docker images, see the [Docker](/deployment-docker) page.

## Push to container registry

Test 
## Deploy to Kubernetes



