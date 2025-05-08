---
title: Deploy Langflow on Docker
slug: /deployment-docker
---

This guide demonstrates deploying Langflow with Docker and Docker Compose.

Three options are available:

* The [Quickstart](#Quickstart-with-SQLite-database) option provides Langflow's default SQLite database. This database is stored in the container's filesystem, which means all data is lost when the container is stopped since no persistent volume is configured.
* The [docker-compose.yml](#clone-the-repo-and-build-the-langflow-docker-container) option builds Langflow with a persistent PostgreSQL database service.
* The [Package your flow as a docker image](#package-your-flow-as-a-docker-image) option demonstrates packaging an existing flow with the Dockerfile.

## Prerequisites

- [Docker](https://docs.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

## Quickstart with a SQLite database

For quick testing and development, create a Dockerfile with Langflow's default SQLite database.
The SQLite database is stored in the container's filesystem, which means all data is lost when the container is stopped since no persistent volume is configured.

To use the Dockerfile:

1. Create a new directory for your project:
   ```bash
   mkdir langflow-docker && cd langflow-docker
   ```

2. Create the Dockerfile with the following configuration.

```dockerfile
# Use the official Langflow image
FROM langflowai/langflow:latest

# Expose the port
EXPOSE 7860

# Run Langflow
CMD ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
```

3. Build and run the container:
   ```bash
   docker build -t langflow-docker .
   docker run -p 7860:7860 langflow-docker
   ```

Langflow is accessible at `http://localhost:7860/`.

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

- `LANGFLOW_DATABASE_URL`: The connection string for the PostgreSQL database.
- `LANGFLOW_CONFIG_DIR`: The directory where Langflow stores logs, file storage, monitor data, and secret keys.

Volumes:

- `langflow-data`: This volume is mapped to `/app/langflow` in the container.

### PostgreSQL service

The `postgres` service is a database that stores Langflow's persistent data including flows, users, and settings.

The service runs on port 5432 and includes a dedicated volume for data storage.

The `postgres` service uses the `postgres:16` Docker image.

Environment variables:

- `POSTGRES_USER`: The username for the PostgreSQL database.
- `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
- `POSTGRES_DB`: The name of the PostgreSQL database.

Volumes:

- `langflow-postgres`: This volume is mapped to `/var/lib/postgresql/data` in the container.

### Deploy a specific Langflow version with Docker Compose

If you want to deploy a specific version of Langflow, you can modify the `image` field under the `langflow` service in the Docker Compose file. For example, to use version `1.0-alpha`, change `langflowai/langflow:latest` to `langflowai/langflow:1.0-alpha`.

## Package your flow as a Docker image

You can include your Langflow flow with the application image.
When you build the image, your saved flow `.JSON` flow is included.
This enables you to serve a flow from a container, push the image to Docker Hub, and deploy on Kubernetes.

An example flow is available in the [Langflow Helm Charts](https://github.com/langflow-ai/langflow-helm-charts/tree/main/examples/flows) repository, or you can provide your own `JSON` file.

1. Create a project directory:

```bash
mkdir langflow-custom && cd langflow-custom
```

2. Download the example flow or include your flow's `.JSON` file in the `langflow-custom`