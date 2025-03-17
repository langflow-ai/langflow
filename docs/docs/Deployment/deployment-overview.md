---
title: Langflow deployment concepts
slug: /deployment-overview
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

You have a flow, and want to share it with the world in a production environment.

This page outlines the journey from locally-run flow to a cloud-hosted production server.

More specific instructions are available in the [Docker](/deployment-docker) and [Kubernetes](/deployment-kubernetes) pages.

## Langflow deployment architecture

Langflow can be deployed as an **IDE** or as a **runtime**.

The **IDE** includes the frontend for visual development of your flow. The default [docker-compose.yml](https://github.com/langflow-ai/langflow/blob/main/docker_example/docker-compose.yml) file hosted in the Langflow repository builds the Langflow IDE image. To deploy the Langflow IDE, see [Docker](/deployment-docker).

The **runtime** is a headless or backend-only mode. The server exposes your flow as an endpoint, and runs only the processes necessary to serve your flow, with PostgreSQL as the database for improved scalability. Use the Langflow **runtime** to deploy your flows, because you don't require the front-end for visual development.

## Package your flow with the Langflow runtime image

To package your flow as a Docker image, copy your flow's `.JSON` file with a command in the Dockerfile.

For example, if you have your flow stored in a directory like this:

```text
LANGFLOW-APPLICATION/
├── flows/
│   ├── flow1.json
│   └── flow2.json
├── Dockerfile
```

Include the `COPY` command in your Dockerfile:

```dockerfile
FROM langflowai/langflow-backend
RUN mkdir -p /app/flows
COPY ./flows/*.json /app/flows/
```

An example [Dockerfile](https://github.com/langflow-ai/langflow-helm-charts/blob/main/examples/langflow-runtime/docker/Dockerfile) for bundling flows is hosted in the Langflow Helm Charts repository.

For a step-by-step example, see [Build applications in Langflow](/platform-build-application).

For more on building the Langflow docker image and pushing it to Docker Hub, see [Package your flow as a docker image](/deployment-docker#package-your-flow-as-a-docker-image).

## Deploy to Kubernetes

Override the values in the [langflow-runtime](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/Chart.yaml) Helm chart to deploy the application.

```text
helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
helm repo update
helm install langflow-runtime langflow/langflow-runtime \
    --set "image.repository=myuser/langflow-hello-world" \
    --set "image.tag=1.0.0"\
```

For more information, refer to [Deploy Langflow on Kubernetes](/deployment-kubernetes).

For more detailed information about database configuration, see [Configure an external PostgreSQL database](/configuration-custom-database).





