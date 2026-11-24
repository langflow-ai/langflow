# Run Langflow with Docker

This guide will help you get Langflow up and running using Docker and Docker Compose.

## Prerequisites

- Docker
- Docker Compose

## Steps

1. Clone the Langflow repository:

   ```sh
   git clone https://github.com/langflow-ai/langflow.git
   ```

2. Navigate to the `docker_example` directory:

   ```sh
   cd langflow/docker_example
   ```

3. Create a `.env` file with the Langflow admin and PostgreSQL passwords set:

   ```text
   LANGFLOW_SUPERUSER_PASSWORD='SUPERUSER_PASSWORD'
   POSTGRES_PASSWORD='POSTGRES_PASSWORD'
   ```

   Replace `SUPERUSER_PASSWORD` with a strong password for the Langflow superuser and `POSTGRES_PASSWORD` with a separate strong password for PostgreSQL.
   The default admin username is `langflow`.

   Keep the single quotes so Compose preserves literal characters such as `$`. Escape an embedded single quote with `\'`. For example, `POSTGRES_PASSWORD='Example$pass\'word'` stores the raw password `Example$pass'word`. The surrounding quotes are not part of the password.

4. Run the Docker Compose file:

   ```sh
   docker compose up
   ```

Langflow will now be accessible at [http://localhost:7860/](http://localhost:7860/).

## Configure Docker Compose

The Docker Compose configuration spins up two services: `langflow` and `postgres`.

### Langflow service

The `langflow` service uses the `langflowai/langflow:latest` Docker image and exposes port 7860. It depends on the `postgres` service. At startup, it constructs `LANGFLOW_DATABASE_URL` with an RFC 3986 percent-encoded password so reserved characters do not change URL parsing.

Environment variables:

- `POSTGRES_PASSWORD`: The raw PostgreSQL password. This value is required in `.env` and is percent-encoded only when constructing `LANGFLOW_DATABASE_URL`.
- `LANGFLOW_SUPERUSER_PASSWORD`: The initial admin password. This value is required in `.env`.
- `LANGFLOW_CONFIG_DIR`: The directory where Langflow stores logs, file storage, monitor data, and secret keys.

Volumes:

- `langflow-data`: This volume is mapped to `/app/langflow` in the container.

### PostgreSQL service

The `postgres` service uses the `postgres:16-trixie` Docker image and is available to Langflow on the private Compose network at `postgres:5432` without publishing port 5432 to the host. The image is pinned to a specific Debian base (`trixie`, Debian 13) so the `postgres:16` tag cannot silently roll its underlying OS, which would otherwise produce a glibc collation version mismatch warning on existing data volumes.

Environment variables:

- `POSTGRES_USER`: The username for the PostgreSQL database.
- `POSTGRES_PASSWORD`: The password for the PostgreSQL database. This value is required in `.env` and is also used in `LANGFLOW_DATABASE_URL`.
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

## Changing the PostgreSQL password during an upgrade

`POSTGRES_PASSWORD` initializes the role password only when PostgreSQL first initializes an empty data directory. Changing it in `.env` does not update the password stored in an existing `langflow-postgres` volume.

Before running Compose commands, create or update `.env` with both required password values shown above. Set `POSTGRES_PASSWORD` to the existing database password and use the literal quoting described above. Compose requires these values even for `stop` and `exec`.

During planned downtime, stop Langflow and open psql for the Compose variant you use:

For `docker-compose.yml`:

```sh
docker compose stop langflow
docker compose exec postgres psql -U langflow -d langflow
```

For `pre.docker-compose.yml`:

```sh
docker compose -f pre.docker-compose.yml stop langflow
docker compose -f pre.docker-compose.yml exec postgres psql -U langflow -d langflow
```

At the psql prompt, rotate the role password and exit:

```text
langflow=# \password langflow
langflow=# \q
```

Enter the new password twice at the secure prompts. psql does not echo the password or include it in a SQL command. Then update `POSTGRES_PASSWORD` in `.env` to the same raw value, keeping the literal quoting described above. Restart with `docker compose up -d` or `docker compose -f pre.docker-compose.yml up -d`. The startup command continues to percent-encode the password when constructing `LANGFLOW_DATABASE_URL`.

## Switching to a specific Langflow version

If you want to use a specific version of Langflow, you can modify the `image` field under the `langflow` service in the Docker Compose file. For example, to use version 1.0-alpha, change `langflowai/langflow:latest` to `langflowai/langflow:1.0-alpha`.
