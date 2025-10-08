# Local Docker Testing Guide

This script allows you to test the Docker container locally with Postgres.

## Prerequisites

- Docker installed and running
- `.env-file` exists in the project root
- Set `VITE_CLERK_PUBLISHABLE_KEY` environment variable (optional)

## Usage

### 1. Build the Docker Image

```bash
./local-docker-test.sh build
```

This builds the Docker image using environment variables from the GitHub staging workflow:
- `VITE_AUTO_LOGIN=false`
- `VITE_CLERK_AUTH_ENABLED=true`
- `VITE_CLERK_PUBLISHABLE_KEY` (from your environment)

### 2. Run the Docker Containers

```bash
./local-docker-test.sh run
```

This starts:
- **Postgres container** on port 5432
- **Langflow container** on port 7860
- Uses environment variables from `.env-file`
- Automatically connects Langflow to Postgres

Access the application at: http://localhost:7860

### 3. Stop the Docker Containers

```bash
./local-docker-test.sh stop
```

This stops and removes:
- Langflow container
- Postgres container
- Docker network

## Configuration

### Postgres Settings
- Database: `langflow`
- User: `langflow`
- Password: `langflow`
- Port: `5432`

These are defined in the script and can be modified if needed.

### Environment Variables

The script uses `.env-file` for runtime configuration. The build uses staging environment variables matching the GitHub workflow.

## Quick Start

```bash
# Make script executable
chmod +x local-docker-test.sh

# Build, run, and test
./local-docker-test.sh build
./local-docker-test.sh run

# When done testing
./local-docker-test.sh stop
```

## Troubleshooting

### Check container logs
```bash
docker logs langflow-local-test
docker logs langflow-postgres-local
```

### Check if containers are running
```bash
docker ps
```

### Connect to Postgres directly
```bash
docker exec -it langflow-postgres-local psql -U langflow -d langflow
```
