---
title: Environment Variables
sidebar_position: 7
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
If you choose to use both sources together, be aware that environment variables imported from a `.env` file take [precedence](#precedence) over those set in your terminal.

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

:::info[CLI precedence]
[Langflow CLI options](./configuration-cli.md) override the value of corresponding environment variables defined in the `.env` file as well as any environment variables set in your terminal.
:::

## Supported variables

The following table lists the environment variables supported by Langflow.

| Variable | Values | Default | Required | Description |
|----------|--------|---------|----------|-------------|
| `BACKEND_URL` | String | `http://localhost:7860/` |  | Value must finish with slash (`/`). |
| `DO_NOT_TRACK` | Boolean | `False` | No | If enabled, Langflow will not track telemetry. |
| `LANGCHAIN_API_KEY` | String | - | Yes | No description available. |
| `LANGCHAIN_PROJECT` | String | `Langflow` | No | No description available. |
| `LANGFLOW_AUTO_LOGIN` |  |  |  | Set AUTO_LOGIN to false if you want to disable auto login and use the login form to login. LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD must be set if AUTO_LOGIN is set to false. |
| `LANGFLOW_AUTO_SAVING` | Boolean | `true` |  | Enable flow auto-saving.<br/>See `--auto-saving` option. |
| `LANGFLOW_AUTO_SAVING_INTERVAL` | Integer | `1000` |  | Set the interval for flow auto-saving in milliseconds.<br/>See `--auto-saving-interval` option. |
| `LANGFLOW_BACKEND_ONLY` | Boolean | `false` |  | Only run Langflow's backend server (no frontend).<br/>See `--backend-only` option. |
| `LANGFLOW_CACHE_TYPE` | `async`<br/>`redis`<br/>`memory`<br/>`disck`<br/>`critical` | `async` |  | Set the cache type for Langflow.<br/>If you set the type to `redis`, then you must also set the following environment variables: `LANGFLOW_REDIS_HOST`, `LANGFLOW_REDIS_PORT`, `LANGFLOW_REDIS_DB`, and `LANGFLOW_REDIS_CACHE_EXPIRE`. |
| `LANGFLOW_COMPONENTS_PATH` | String | `langflow/components` | Yes | Path to the directory containing custom components.<br/>See `--components-path` option. |
| `LANGFLOW_CONFIG_DIR` | String |  |  | Set the Langflow configuration directory where files, logs, and the Langflow database are stored. |
| `LANGFLOW_DATABASE_URL` | String | None | Yes | Set the database URL for Langflow. If you don't provide one, Langflow uses an SQLite database. |
| `LANGFLOW_DEV` | Boolean | `false` |  | Run Langflow in development mode (may contain bugs).<br/>See `--dev` option. |
| `LANGFLOW_DOWNLOAD_WEBHOOK_UR` |  |  |  | No description available. |
| `LANGFLOW_FALLBACK_TO_ENV_VAR` | Boolean | `true` |  | If enabled, [global variables](../Settings/settings-global-variables.md) set in the Langflow UI fall back to an environment variable with the same name when Langflow fails to retrieve the variable value. |
| `LANGFLOW_FRONTEND_PATH` | String | `./frontend` |  | Path to the frontend directory containing build files. This is for development purposes only.<br/>See `--frontend-path` option. |
| `LANGFLOW_HEALTH_CHECK_MAX_RETRIES` | Integer | `5` |  | Set the maximum number of retries for the health check.<br/>See `--health-check-max-retries` option. |
| `LANGFLOW_HOST` | String | `127.0.0.1` |  | The host on which the Langflow server will run.<br/>See `--host` option. |
| `LANGFLOW_LANGCHAIN_CACHE` | `InMemoryCache`<br/>`SQLiteCache` | `InMemoryCache` | Yes | Type of cache to use.<br/>See `--cache` option. |
| `LANGFLOW_LIKE_WEBHOOK_URL` |  |  |  | No description available. |
| `LANGFLOW_LOG_ENV` | String | `` | No | No description available. |
| `LANGFLOW_LOG_FILE` | String | `logs/langflow.log` | No | Set the path to the log file for Langflow.<br/>See `--log-file` option. |
| `LANGFLOW_LOG_LEVEL` | String | `critical` | Yes | Set the logging level.<br/>See `--log-level` option. |
| `LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE` | integer | `0` | No | No description available. |
| `LANGFLOW_MAX_FILE_SIZE_UPLOAD` | Integer | `100` |  | Set the maximum file size for the upload in megabytes.<br/>See `--max-file-size-upload` option. |
| `LANGFLOW_OPEN_BROWSER` | Boolean | `true` |  | Open the system web browser on startup.<br/> See `--open-browser` option. |
| `LANGFLOW_PORT` | Integer | `7860` |  | The port on which the Langflow server will run. The server automatically selects a free port if the specified port is in use.<br/>See `--port` option. |
| `LANGFLOW_PROMETHEUS_ENABLED` | Boolean | `false` |  | Expose Prometheus metrics. |
| `LANGFLOW_PROMETHEUS_PORT` | Integer | `9090` | Yes | Set the port on which Langflow exposes Prometheus metrics. |
| `LANGFLOW_REDIS_CACHE_EXPIRE` | Integer | `3600` |  | See `LANGFLOW_CACHE_TYPE` variable. |
| `LANGFLOW_REDIS_DB ` | Integer | `0` |  | See `LANGFLOW_CACHE_TYPE` variable. |
| `LANGFLOW_REDIS_HOST` | String | `localhost` | Yes | See `LANGFLOW_CACHE_TYPE` variable. |
| `LANGFLOW_REDIS_PORT` | String | `6379` | Yes | See `LANGFLOW_CACHE_TYPE` variable. |
| `LANGFLOW_REMOVE_API_KEYS` | Boolean | `false` |  | Remove API keys from the projects saved in the database.<br/> See `--remove-api-keys` option. |
| `LANGFLOW_SAVE_DB_IN_CONFIG_DIR` | Boolean | `false` |  | Save the Langflow database in `LANGFLOW_CONFIG_DIR` instead of in the Langflow package directory. Note, when this variable is set to default (`false`), the database isn't shared between different virtual environments and the database is deleted when you uninstall Langflow. |
| `LANGFLOW_STORE` | Boolean | `true` |  | Enable the Langflow Store.<br/>See `--store` option. |
| `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` | Boolean | `true` |  | Store environment variables as Global Variables in the database. |
| `LANGFLOW_SUPERUSER` |  |  |  | Specify the name for the superuser.<br/>See `--username` option. |
| `LANGFLOW_SUPERUSER_PASSWORD` |  |  |  | Specify the password for the superuser.<br/>See `--password` option. |
| `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` | String | None |  | Comma-separated list of environment variables to get from the environment and store as [global variables](../Settings/settings-global-variables.md). |
| `LANGFLOW_WORKER_TIMEOUT` | Integer | `300` |  | Worker timeout in seconds.<br/>See `--worker-timeout` option. |
| `LANGFLOW_WORKERS` | Integer | `1` |  | Number of worker processes.<br/>See `--workers` option. |
| `LANGFUSE_HOST` | String | `-` | No | No description available. |
| `LANGFUSE_PUBLIC_KEY` | String | `-` | No | No description available. |
| `LANGFUSE_SECRET_KEY` | String | `-` | No | No description available. |
| `OPENAI_API_KEY` | String | - | Yes | No description available. |
| `RABBITMQ_DEFAULT_PASS` | String | `langflow` | No | No description available. |
| `RABBITMQ_DEFAULT_USER` | String | `langflow` | No | RabbitMQ. |
| `RESULT_BACKEND` | String | `redis://localhost:6379/0` | No | No description available. |


## Removed

| Variable | Values | Default | Required | Description |
|----------|--------|---------|----------|-------------|
| `ASTRA_ENHANCED` | Boolean | `false` | No | No description available. |

