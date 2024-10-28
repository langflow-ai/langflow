---
title: Environment Variables (NEW)
sidebar_position: 8
slug: /environment-variables
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Environment Variables

Langflow lets you configure a number of settings using environment variables.

## Configure environment variables

Langflow recognizes supported environment variables from the following sources:

- Environment variables that you've set in your terminal.
- Environment variables that you've imported from a `.env` file using the `--env-file` option in the Langflow CLI.

You can choose to use one source exclusively, or use both sources together.
If you choose to use both sources together, be aware that environment variables imported from a `.env` file take precedence over those set in your terminal.
For more information, see [Environment variable precedence](#precedence).

### Set environment variables in your terminal {#configure-variables-terminal}

Run the following commands to set environment variables for your current terminal session:

<Tabs>

<TabItem value="linux-macos" label="Linux or macOS" default>
```bash
export VARIABLE_NAME='VALUE'
```
</TabItem>

<TabItem value="windows" label="Windows" default>
```
set VARIABLE_NAME='VALUE'
```
</TabItem>

<TabItem value="docker" label="Docker" default>
```bash
docker run -it --rm \
    -p 7860:7860 \
    -e VARIABLE_NAME='VALUE' \
    langflowai/langflow:latest
```
</TabItem>

</Tabs>

When you start Langflow, it looks for environment variables that you've set in your terminal.
If it detects a supported environment variable, then it automatically adopts the specified value, subject to [precedence rules](#precedence).

### Import environment variables from a .env file {#configure-variables-env-file}

1. Create a `.env` file and open it in your preferred editor.

2. Add your environment variables to the file:

    ```plaintext title=".env"
    VARIABLE_NAME='VALUE'
    VARIABLE_NAME='VALUE'
    ```

    :::info
    The Langflow project includes a [`.env.example`](https://github.com/langflow-ai/langflow/blob/main/.env.example) file to help you get started.
    You can copy the contents of this file into your own `.env` file and replace the example values with your own preferred settings.
    :::

3. Save and close the file.

4. Start Langflow using the `--env-file` option to define the path to your `.env` file:

   <Tabs>

    <TabItem value="local" label="Local" default>
    ```bash
    python -m langflow run --env-file .env
    ```
    </TabItem>

    <TabItem value="docker" label="Docker" default>
    ```bash
    docker run -it --rm \
        -p 7860:7860 \
        --env-file .env \
        langflowai/langflow:latest
    ```
    </TabItem>

    </Tabs>

On startup, Langflow imports the environment variables from your `.env` file, as well as any that you [set in your terminal](#configure-variables-terminal), and adopts their specified values.

## Precedence {#precedence}

Environment variables [defined in the .env file](#configure-variables-env-file) take precedence over those [set in your terminal](#configure-variables-terminal).
That means, if you happen to set the same environment variable in both your terminal and your `.env` file, Langflow adopts the value from the the `.env` file.

For example, let's say you set the `LANGFLOW_PORT` environment variable to `7860` in your terminal:

```bash
export LANGFLOW_PORT=7860
```

But you also happened to set the `LANGFLOW_PORT` environment variable to **`7870`** in your `.env` file:

```title=".env"
LANGFLOW_PORT=7870
```

Then, if you started Langflow with the `--env-file` option:

```bash
python -m langflow run --env-file .env
```

Langflow would set the port to  **`7870`** (the value from the `.env` file).

:::info[CLI precedence]
Langflow CLI options override the value of corresponding environment variables defined in the `.env` file as well as any environment variables set in your terminal.

For example, if you were to add the `--port` option to the command in the previous example:

```bash
python -m langflow run --port 7880 --env-file .env
```

Langflow would set the port to **`7880`** (the value passed with the CLI).
:::

## Environment variables reference

The following table lists the environment variables supported by Langflow.

| `` |  |  |  | No description available. |

| Variable | Values | Default | Required | Description |
|----------|--------|---------|----------|-------------|
| `ASTRA_ENHANCED` | Boolean | `false` | No | No description available. |
| `BACKEND_URL` |  | `http://localhost:7860/` |  | Value must finish with slash (`/`). |
| `BROKER_URL` | String | - | Yes | No description available. |
| `DO_NOT_TRACK` | Boolean | `False` | No | No description available. |
| `LANGCHAIN_API_KEY` | String | - | Yes | No description available. |
| `LANGCHAIN_PROJECT` | String | `Langflow` | No | No description available. |
| `LANGFLOW_AUTO_LOGIN` |  |  |  | Set AUTO_LOGIN to false if you want to disable auto login and use the login form to login. LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD must be set if AUTO_LOGIN is set to false. |
| `LANGFLOW_AUTO_SAVING` |  |  |  | No description available. |
| `LANGFLOW_BACKEND_ONLY` |  |  |  | No description available. |
| `LANGFLOW_CACHE` |  |  |  | No description available. |
| `LANGFLOW_CACHE_TYPE` | async, memory, redis | memory |  | Whether to use RedisCache or ThreadingInMemoryCache or AsyncInMemoryCache. If you want to use redis then the following environment variables must be set: LANGFLOW_REDIS_HOST, LANGFLOW_REDIS_PORT, LANGFLOW_REDIS_DB, LANGFLOW_REDIS_CACHE_EXPIRE. |
| `LANGFLOW_COMPONENTS_PATH` | String | - | Yes | No description available. |
| `LANGFLOW_CONFIG_DIR` | String | `~/.langflow`? |  | Langflow configuration directory where files, logs and database will be stored. |
| `LANGFLOW_DATABASE_URL` | String | `sqlite:///./langflow.db`? | Yes | Database URL. Postgres example: `postgresql://postgres:postgres@localhost:5432/langflow` |
| `LANGFLOW_DEV` |  |  |  | No description available. |
| `LANGFLOW_DOWNLOAD_WEBHOOK_UR` |  |  |  | No description available. |
| `LANGFLOW_FRONTEND_PATH` |  |  |  | Path to the frontend directory containing build files. |
| `LANGFLOW_HOST` |  | `127.0.0.1` |  | Server host. |
| `LANGFLOW_LANGCHAIN_CACHE` | String | - | Yes | Cache type. |
| `LANGFLOW_LIKE_WEBHOOK_URL` |  |  |  | No description available. |
| `LANGFLOW_LOG_ENV` | String | `` | No | No description available. |
| `LANGFLOW_LOG_FILE` | String | `logs/langflow.log` | No | Path to the log file. |
| `LANGFLOW_LOG_LEVEL` | String | `critical` | Yes | No description available. |
| `LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE` | integer | `0` | No | No description available. |
| `LANGFLOW_OPEN_BROWSER` |  |  |  | No description available. |
| `LANGFLOW_PORT` |  |  |  | No description available. |
| `LANGFLOW_PROMETHEUS_PORT` | String | - | Yes | No description available. |
| `LANGFLOW_REDIS_CACHE_EXPIRE` |  | `3600` |  | No description available. |
| `LANGFLOW_REDIS_DB ` |  | `0` |  | No description available. |
| `LANGFLOW_REDIS_HOST` | String | `localhost` | Yes | No description available. |
| `LANGFLOW_REDIS_PORT` | String | `6379` | Yes | No description available. |
| `LANGFLOW_REMOVE_API_KEYS` |  |  |  | Whether to remove API keys from the projects saved in the database. |
| `LANGFLOW_SAVE_DB_IN_CONFIG_DIR` | Boolean |  |  | Save Langflow's internal database in the config directory. If false, the database will be saved in Langflow's root directory. This means that the database will be deleted when Langflow is uninstalled and that the database will not be shared between different virtual environments. |
| `LANGFLOW_STORE` |  |  |  | No description available. |
| `LANGFLOW_STORE_URL` |  | `https://api.langflow.store` |  | No description available. |
| `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` |  |  |  | No description available. |
| `LANGFLOW_SUPERUSER` |  |  |  | No description available. |
| `LANGFLOW_SUPERUSER_PASSWORD` |  |  |  | No description available. |
| `LANGFLOW_WORKERS` |  | `1` |  | Worker processes. |
| `LANGFUSE_HOST` | String | `-` | No | No description available. |
| `LANGFUSE_PUBLIC_KEY` | String | `-` | No | No description available. |
| `LANGFUSE_SECRET_KEY` | String | `-` | No | No description available. |
| `OPENAI_API_KEY` | String | - | Yes | No description available. |
| `RABBITMQ_DEFAULT_PASS` | String | `langflow` | No | No description available. |
| `RABBITMQ_DEFAULT_USER` | String | `langflow` | No | RabbitMQ. |
| `RESULT_BACKEND` | String | `redis://localhost:6379/0` | No | No description available. |


## Details

### ASTRA_ENHANCED

No description available

**Details:**
- **Type:** `boolean`
- **Required:** No
- **Default:** `false`
- **Source:** `backend/base/langflow/components/vectorstores/astradb.py`

### BROKER_URL

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/core/celeryconfig.py`

### DO_NOT_TRACK

No description available

**Details:**
- **Type:** `boolean`
- **Required:** No
- **Default:** `False`
- **Source:** `backend/base/langflow/services/telemetry/service.py`

### LANGCHAIN_API_KEY

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/services/tracing/langsmith.py`

### LANGCHAIN_PROJECT

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `Langflow`
- **Source:** `backend/base/langflow/services/tracing/service.py`

### LANGFLOW_COMPONENTS_PATH

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/services/settings/base.py`

### LANGFLOW_DATABASE_URL

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/services/settings/base.py`

### LANGFLOW_LANGCHAIN_CACHE

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/interface/utils.py`

### LANGFLOW_LOG_ENV

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** ``
- **Source:** `backend/base/langflow/logging/logger.py`

### LANGFLOW_LOG_FILE

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** ``
- **Source:** `backend/base/langflow/logging/logger.py`

### LANGFLOW_LOG_LEVEL

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/logging/logger.py`

### LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE

No description available

**Details:**
- **Type:** `integer`
- **Required:** No
- **Default:** `0`
- **Source:** `backend/base/langflow/logging/logger.py`

### LANGFLOW_PROMETHEUS_PORT

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/main.py`

### LANGFLOW_REDIS_HOST

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/core/celeryconfig.py`

### LANGFLOW_REDIS_PORT

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/base/langflow/core/celeryconfig.py`

### LANGFUSE_HOST

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `-`
- **Source:** `backend/base/langflow/services/tracing/langfuse.py`

### LANGFUSE_PUBLIC_KEY

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `-`
- **Source:** `backend/base/langflow/services/tracing/langfuse.py`

### LANGFUSE_SECRET_KEY

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `-`
- **Source:** `backend/base/langflow/services/tracing/langfuse.py`

### OPENAI_API_KEY

No description available

**Details:**
- **Type:** `str`
- **Required:** Yes
- **Source:** `backend/tests/unit/graph/graph/test_cycles.py`

### RABBITMQ_DEFAULT_PASS

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `langflow`
- **Source:** `backend/base/langflow/core/celeryconfig.py`

### RABBITMQ_DEFAULT_USER

RabbitMQ

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `langflow`
- **Source:** `backend/base/langflow/core/celeryconfig.py`

### RESULT_BACKEND

No description available

**Details:**
- **Type:** `str`
- **Required:** No
- **Default:** `redis://localhost:6379/0`
- **Source:** `backend/base/langflow/core/celeryconfig.py`



---
*This documentation was automatically generated on 2024-10-23.*
