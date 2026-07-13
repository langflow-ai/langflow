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

3. Create a `.env` file with the LangFlow admin password:

   ```sh
   LANGFLOW_SUPERUSER_PASSWORD=replace-with-a-strong-password
   ```

   The default admin username is `langflow`.

4. Run the Docker Compose file:

   ```sh
   docker compose up
   ```

LangFlow will now be accessible at [http://localhost:7860/](http://localhost:7860/).

## Docker Compose Configuration

The Docker Compose configuration spins up two services: `langflow` and `postgres`.

### LangFlow Service

The `langflow` service uses the `langflowai/langflow:latest` Docker image and exposes port 7860. It depends on the `postgres` service.

Environment variables:

- `LANGFLOW_DATABASE_URL`: The connection string for the PostgreSQL database.
- `LANGFLOW_SUPERUSER_PASSWORD`: The initial admin password. This value is required in `.env`.
- `LANGFLOW_CONFIG_DIR`: The directory where LangFlow stores logs, file storage, monitor data, and secret keys.

Volumes:

- `langflow-data`: This volume is mapped to `/app/langflow` in the container.

### PostgreSQL Service

The `postgres` service uses the `postgres:16-trixie` Docker image and exposes port 5432. The image is pinned to a specific Debian base (`trixie`, Debian 13) so the `postgres:16` tag cannot silently roll its underlying OS, which would otherwise produce a glibc collation version mismatch warning on existing data volumes.

Environment variables:

- `POSTGRES_USER`: The username for the PostgreSQL database.
- `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
- `POSTGRES_DB`: The name of the PostgreSQL database.

Volumes:

- `langflow-postgres`: This volume is mapped to `/var/lib/postgresql/data` in the container.

### Upgrading from a `bookworm`-initialized volume

Earlier versions of this example used `postgres:16`, which initially shipped on Debian Bookworm (glibc 2.36). The pinned image now uses Trixie (glibc 2.41). On the first start against a volume that was initialized under Bookworm, PostgreSQL logs a one-time warning:

```
WARNING: database "langflow" has a collation version mismatch
DETAIL: The database was created using collation version 2.36, but the operating system provides version 2.41.
```

To clear it, refresh the collation version against the running database (one-off, takes seconds on a typical Langflow database):

```sh
docker compose exec postgres \
  psql -U langflow -d langflow \
  -c "REINDEX DATABASE langflow;" \
  -c "ALTER DATABASE langflow REFRESH COLLATION VERSION;"
```

Fresh installs are unaffected.

## Switching to a Specific LangFlow Version

If you want to use a specific version of LangFlow, you can modify the `image` field under the `langflow` service in the Docker Compose file. For example, to use version 1.0-alpha, change `langflowai/langflow:latest` to `langflowai/langflow:1.0-alpha`.
