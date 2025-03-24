---
title: Build an application in Langflow
slug: /build-application
---

This guide walks you through the process of building an application using Langflow.
You'll learn how to set up a project directory, manage dependencies, configure environment variables, and package your Langflow application in a Docker container, or run it locally.

To deploy your application to Docker or Kubernetes, see [Deployment](/deployment-overview).

## Create a project directory

Create a project directory similar to this one.

```text
LANGFLOW-APPLICATION/
├── flows/
│   ├── flow1.json
│   └── flow2.json
├── langflow-config-dir/
├── docker.env
├── Dockerfile
├── README.md
```

The `/flows` folder holds the flows you want to host.

The `langflow-config-dir` is referenced in the Dockerfile as the location for Langflow's configuration files, database, and logs. For more information, see [Environment variables](/environment-variables).

The `docker.env` file is copied to the Docker image as a `.env` file in the container root. This file controls Langflow's behavior, holds secrets, and configures runtime settings like authentication, database storage, API keys, and server configurations.

The `Dockerfile` controls how your image is built. This file copies your flows and `docker.env` files to your image.

### Package management

The base Docker image includes the Langflow core dependencies by using `langflowai/langflow:latest` as the parent image.

If your application requires additional dependencies, create a `pyproject.toml` file and add the dependencies to the file. For more information, see [Install custom dependencies](/install-custom-dependencies).

To deploy the application with the additional dependencies to Docker, copy the `pyproject.toml` and `uv.lock` files to the Docker image by adding the following to the Dockerfile.

```text
COPY pyproject.toml uv.lock /app/
```

## Environment variables

The `docker.env` file is a `.env` file loaded into your Docker image.

This example `docker.env` defines auto-login behavior and which port to expose. Your environment may vary. For more information, see [Environment variables](/environment-variables).

```text
LANGFLOW_AUTO_LOGIN=true
LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true
LANGFLOW_BASE_URL=http://0.0.0.0:7860
OPENAI_API_KEY=sk-...
```

## Add flows and components

Add your flows `.JSON` files to the `/flows` folder.

To export your flows from Langflow, see [Flows](/Concepts/concepts-flows).

Optionally, add any custom components to a `/components` folder, and specify the path in your `docker.env`.

## Package your Langflow project in a Docker image

1. Add the following commands to your Dockerfile.

```dockerfile
# Use the latest version of langflow
FROM langflowai/langflow:latest

# Create accessible folders and set the working directory in the container
RUN mkdir /app/flows
RUN mkdir /app/langflow-config-dir
WORKDIR /app

# Copy the flows, optional components, and langflow-config-dir folders to the container
COPY flows /app/flows
COPY components /app/components
COPY langflow-config-dir /app/langflow-config-dir

# copy docker.env file
COPY docker.env /app/.env

# Set environment variables
ENV PYTHONPATH=/app
ENV LANGFLOW_LOAD_FLOWS_PATH=/app/flows
ENV LANGFLOW_CONFIG_DIR=/app/langflow-config-dir
ENV LANGFLOW_COMPONENTS_PATH=/app/components
ENV LANGFLOW_LOG_ENV=container

# Command to run the server
EXPOSE 7860
CMD ["langflow", "run", "--backend-only", "--env-file","/app/.env","--host", "0.0.0.0", "--port", "7860"]
```

The environment variables set in the Dockerfile specify resource paths and allow Langflow to access them. Values from `docker.env` will override the values set in the Dockerfile. Additionally, logging behavior is set here with `ENV LANGFLOW_LOG_ENV=container` for serialized JSON to `stdout`. For more information on configuring logs, see [Logging](/logging).

:::note
Optionally, remove the `--backend-only` flag from the startup command to start Langflow with the frontend enabled.
For more on `--backend-only` mode and the Langflow Docker image, see [Docker](/deployment-docker).
:::

2. Save your Dockerfile.
3. Build the Docker image:
```bash
docker build -t langflow-pokedex:1.2.0 .
```
4. Run the Docker container:
```bash
docker run -p 7860:7860 langflow-pokedex:1.2.0
```

:::note
For instructions on building and pushing your image to Docker Hub, see [Docker](/deployment-docker).
:::

5. Confirm the server is serving your flows.
Open a `.JSON` file in your `/flows` folder and find the file's `id` value. It's the first value in the flow document.

```json
"id": "e4167236-938f-4aca-845b-21de3f399858",
```

6. Add this value as the `flow-id` to a POST request to the `/run` endpoint:

```bash
curl -X POST \
    "http://localhost:7860/api/v1/run/e4167236-938f-4aca-845b-21de3f399858?stream=true" \
    -H 'Content-Type: application/json' \
    -d '{
    "input_value": "Tell me about Charizard please",
    "output_type": "chat",
    "input_type": "chat"
}'
```

If the flow streams the result back to you, your flow is being served, and can be consumed from a front-end application by submitting POST requests to this endpoint.

:::note
The test application returns a large amount of text, so the example command used `?stream=true`. If you prefer, set `?stream=false` to use batching. For more information, see the [API examples](/api-reference-api-examples#run-flow).
:::

## Deploy to Docker Hub and Kubernetes

For instructions on building and pushing your image to Docker Hub, see [Docker](/deployment-docker).

To deploy your application to Kubernetes, see [Kubernetes](/deployment-kubernetes).

## Local Development

If you prefer to run the application locally without Docker, follow these steps:

1. Create a Python virtual environment (Python 3.10-3.13 required):
```bash
uv venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
```

2. Install the project dependencies:
```bash
uv pip install langflow
```

If your application requires additional dependencies, see [Install custom dependencies](/install-custom-dependencies).

3. To set up your environment variables, create a `.env` file, and add your required API keys and configurations.

4. Start the Langflow server with the values from your `.env` file:
```bash
uv run langflow run --env-file .env
```

The Langflow server is available by default at `http://localhost:7860`.


