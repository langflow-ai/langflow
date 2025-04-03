---
title: Deploy Langflow on Docker
slug: /deployment-docker
---

This guide demonstrates deploying Langflow with Docker and Docker Compose.

## Prerequisites

* [Docker](https://docs.docker.com/)
* [Docker Compose](https://docs.docker.com/compose/)

## Clone the repo and build the Langflow Docker container

1. Clone the Langflow repository:

	`git clone https://github.com/langflow-ai/langflow.git`

2. Navigate to the `docker_example` directory:

	`cd langflow/docker_example`

3. Run the Docker Compose file:

	`docker compose up`


Langflow is now accessible at `http://localhost:7860/`.

## Configure Docker services

The Docker Compose configuration spins up two services: `langflow` and `postgres`.

To configure values for these services at container startup, include them in your `.env` file.

An example `.env` file is available in the [project repository](https://github.com/langflow-ai/langflow/blob/main/.env.example).

To pass the `.env` values at container startup, include the flag in your `docker run` command:

```
docker run -it --rm \
    -p 7860:7860 \
    --env-file .env \
    langflowai/langflow:latest
```

### Langflow service

The `langflow`service serves both the backend API and frontend UI of the Langflow web application.

The `langflow` service uses the `langflowai/langflow:latest` Docker image and exposes port `7860`. It depends on the `postgres` service.

Environment variables:

* `LANGFLOW_DATABASE_URL`: The connection string for the PostgreSQL database.
* `LANGFLOW_CONFIG_DIR`: The directory where Langflow stores logs, file storage, monitor data, and secret keys.

Volumes:

* `langflow-data`: This volume is mapped to `/app/langflow` in the container.

### PostgreSQL service

The `postgres` service is a database that stores Langflow's persistent data including flows, users, and settings.

The service runs on port 5432 and includes a dedicated volume for data storage.

The `postgres` service uses the `postgres:16` Docker image.

Environment variables:

* `POSTGRES_USER`: The username for the PostgreSQL database.
* `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
* `POSTGRES_DB`: The name of the PostgreSQL database.

Volumes:

* `langflow-postgres`: This volume is mapped to `/var/lib/postgresql/data` in the container.

### Deploy a specific Langflow version with Docker Compose

If you want to deploy a specific version of Langflow, you can modify the `image` field under the `langflow` service in the Docker Compose file. For example, to use version `1.0-alpha`, change `langflowai/langflow:latest` to `langflowai/langflow:1.0-alpha`.

## Package your flow as a Docker image

You can include your Langflow flow with the application image.
When you build the image, your saved flow `.JSON` flow is included.
This enables you to serve a flow from a container, push the image to Docker Hub, and deploy on Kubernetes.

An example flow is available in the [Langflow Helm Charts](https://github.com/langflow-ai/langflow-helm-charts/tree/main/examples/flows) repository, or you can provide your own `JSON` file.

1. Create a project directory:
```shell
mkdir langflow-custom && cd langflow-custom
```

2. Download the example flow or include your flow's `.JSON` file in the `langflow-custom` directory.

```shell
wget https://raw.githubusercontent.com/langflow-ai/langflow-helm-charts/refs/heads/main/examples/flows/basic-prompting-hello-world.json
```

3. Create a Dockerfile:
```dockerfile
FROM langflowai/langflow-backend:latest
RUN mkdir /app/flows
COPY ./*json /app/flows/.
```
The `COPY ./*json` command copies all JSON files in your current directory to the `/flows` folder.

4. Build and run the image locally.
```shell
docker build -t myuser/langflow-hello-world:1.0.0 .
docker run -p 7860:7860 myuser/langflow-hello-world:1.0.0
```

5. Build and push the image to Docker Hub.
Replace `myuser` with your Docker Hub username.
```shell
docker build -t myuser/langflow-hello-world:1.0.0 .
docker push myuser/langflow-hello-world:1.0.0
```

To deploy the image with Helm, see [Langflow runtime deployment](/deployment-kubernetes#deploy-the-langflow-runtime).

