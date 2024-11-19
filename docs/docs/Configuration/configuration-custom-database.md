---
title: External Database Configuration
sidebar_position: 8
---

# External Database Configuration

By default, Langflow uses SQLite as its database. However, you can configure Langflow to use PostgreSQL for production environments.

## Configure PostgreSQL

Set the `LANGFLOW_DATABASE_URL` environment variable with your PostgreSQL connection string:

```bash
export LANGFLOW_DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

Or add it to your `.env` file:

```plaintext
LANGFLOW_DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

When running Langflow make sure to pass the `.env` file in the commmand:

```bash
langflow run --env-file .env
```

## Connection String Format

- **SQLite** (default): `sqlite:///./langflow.db`
- **PostgreSQL**: `postgresql://user:password@host:port/dbname`

## Example Docker Setup

When using Docker, you can set the database URL in your docker-compose file:

```yaml
services:
  langflow:
    image: langflow-ai/langflow:latest
    environment:
      - LANGFLOW_DATABASE_URL=postgresql://user:password@postgres:5432/langflow
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=langflow
```
