# Running LangFlow with Docker

This guide will help you get LangFlow up and running using Docker and Docker Compose.

## Prerequisites

- Docker
- Docker Compose

## Steps

1. Clone the LangFlow repository:

   ```sh
   git clone https://github.com/langflow-ai/langflow.git
   ```

2. Navigate to the `docker_example` directory:

   ```sh
   cd langflow/docker_example
   ```

3. Run the Docker Compose file:

   ```sh
   docker compose up
   ```

LangFlow will now be accessible at [http://localhost:7860/](http://localhost:7860/).

## Docker Compose Configuration

The Docker Compose configuration spins up two services: `langflow` and `postgres`.

### LangFlow Service

The `langflow` service uses the `langflowai/langflow:latest` Docker image and exposes port 7860. It depends on the `postgres` service. To ensure the service has the necessary permissions to create and access files in `/var/lib/langflow`, it is run as the root user.

Environment variables:

- `LANGFLOW_DATABASE_URL`: The connection string for the PostgreSQL database.
- `LANGFLOW_CONFIG_DIR`: The directory where LangFlow stores logs, file storage, monitor data, and secret keys.

Volumes:

- `langflow-data`: This volume is mapped to `/var/lib/langflow` in the container.

### PostgreSQL Service

The `postgres` service uses the `postgres:16` Docker image and exposes port 5432.

Environment variables:

- `POSTGRES_USER`: The username for the PostgreSQL database.
- `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
- `POSTGRES_DB`: The name of the PostgreSQL database.

Volumes:

- `langflow-postgres`: This volume is mapped to `/var/lib/postgresql/data` in the container.

## Switching to a Specific LangFlow Version

If you want to use a specific version of LangFlow, you can modify the `image` field under the `langflow` service in the Docker Compose file. For example, to use version 1.0-alpha, change `langflowai/langflow:latest` to `langflowai/langflow:1.0-alpha`.

## Running as Root User

The Docker Compose configuration specifies that the `langflow` service runs as the root user. This is necessary to avoid permission issues when accessing or creating files in directories owned by root or another user inside the container. While running containers as root can have security implications, it is a common practice for overcoming permission issues in development environments. Ensure to follow best practices for securing your Docker containers in production environments.
