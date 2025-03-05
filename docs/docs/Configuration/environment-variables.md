---
title: Environment variables
slug: /environment-variables
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Link from '@docusaurus/Link';


Langflow lets you configure a number of settings using environment variables.

## Configure environment variables

Langflow recognizes [supported environment variables](#supported-variables) from the following sources:

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

    :::tip
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

## Supported environment variables {#supported-variables}

The following table lists the environment variables supported by Langflow.

| Variable | Format / Values | Default | Description |
|----------|---------------|---------|-------------|
| <Link id="DO_NOT_TRACK"/>`DO_NOT_TRACK` | Boolean | `false` | If enabled, Langflow will not track telemetry. |
| <Link id="LANGFLOW_AUTO_LOGIN"/>`LANGFLOW_AUTO_LOGIN` | Boolean | `true` | Enable automatic login for Langflow. Set to `false` to disable automatic login and require the login form to log into the Langflow UI. Setting to `false` requires [`LANGFLOW_SUPERUSER`](#LANGFLOW_SUPERUSER) and [`LANGFLOW_SUPERUSER_PASSWORD`](environment-variables.md#LANGFLOW_SUPERUSER_PASSWORD) to be set. |
| <Link id="LANGFLOW_AUTO_SAVING"/>`LANGFLOW_AUTO_SAVING` | Boolean | `true` | Enable flow auto-saving.<br/>See [`--auto-saving` option](./configuration-cli.md#run-auto-saving). |
| <Link id="LANGFLOW_AUTO_SAVING_INTERVAL"/>`LANGFLOW_AUTO_SAVING_INTERVAL` | Integer | `1000` | Set the interval for flow auto-saving in milliseconds.<br/>See [`--auto-saving-interval` option](./configuration-cli.md#run-auto-saving-interval). |
| <Link id="LANGFLOW_BACKEND_ONLY"/>`LANGFLOW_BACKEND_ONLY` | Boolean | `false` | Only run Langflow's backend server (no frontend).<br/>See [`--backend-only` option](./configuration-cli.md#run-backend-only). |
| <Link id="LANGFLOW_CACHE_TYPE"/>`LANGFLOW_CACHE_TYPE` | `async`<br/>`redis`<br/>`memory`<br/>`disk`<br/>`critical` | `async` | Set the cache type for Langflow.<br/>If you set the type to `redis`, then you must also set the following environment variables: [`LANGFLOW_REDIS_HOST`](#LANGFLOW_REDIS_HOST), [`LANGFLOW_REDIS_PORT`](#LANGFLOW_REDIS_PORT), [`LANGFLOW_REDIS_DB`](#LANGFLOW_REDIS_DB), and [`LANGFLOW_REDIS_CACHE_EXPIRE`](#LANGFLOW_REDIS_CACHE_EXPIRE). |
| <Link id="LANGFLOW_COMPONENTS_PATH"/>`LANGFLOW_COMPONENTS_PATH` | String | `langflow/components` | Path to the directory containing custom components.<br/>See [`--components-path` option](./configuration-cli.md#run-components-path). |
| <Link id="LANGFLOW_CONFIG_DIR"/>`LANGFLOW_CONFIG_DIR` | String | **Linux/WSL**: `~/.cache/langflow/`<br/>**macOS**: `/Users/<username>/Library/Caches/langflow/`<br/>**Windows**: `%LOCALAPPDATA%\langflow\langflow\Cache` | Set the Langflow configuration directory where files, logs, and the Langflow database are stored. |
| <Link id="LANGFLOW_DATABASE_URL"/>`LANGFLOW_DATABASE_URL` | String | Not set | Set the database URL for Langflow. If not provided, Langflow will use a SQLite database. |
| <Link id="LANGFLOW_DATABASE_CONNECTION_RETRY"/>`LANGFLOW_DATABASE_CONNECTION_RETRY` | Boolean | `false` | If True, Langflow will retry to connect to the database if it fails. |
| <Link id="LANGFLOW_DB_POOL_SIZE"/>`LANGFLOW_DB_POOL_SIZE` | Integer | `10` | **DEPRECATED:** Use `LANGFLOW_DB_CONNECTION_SETTINGS` instead. The number of connections to keep open in the connection pool. |
| <Link id="LANGFLOW_DB_MAX_OVERFLOW"/>`LANGFLOW_DB_MAX_OVERFLOW` | Integer | `20` | **DEPRECATED:** Use `LANGFLOW_DB_CONNECTION_SETTINGS` instead. The number of connections to allow that can be opened beyond the pool size. |
| <Link id="LANGFLOW_DB_CONNECT_TIMEOUT"/>`LANGFLOW_DB_CONNECT_TIMEOUT` | Integer | `20` | The number of seconds to wait before giving up on a lock to be released or establishing a connection to the database. |
| <Link id="LANGFLOW_DB_CONNECTION_SETTINGS"/>`LANGFLOW_DB_CONNECTION_SETTINGS` | JSON | Not set | A JSON dictionary to centralize database connection parameters. Example: `{"pool_size": 10, "max_overflow": 20}` |
| <Link id="LANGFLOW_DEV"/>`LANGFLOW_DEV` | Boolean | `false` | Run Langflow in development mode (may contain bugs).<br/>See [`--dev` option](./configuration-cli.md#run-dev). |
| <Link id="LANGFLOW_FALLBACK_TO_ENV_VAR"/>`LANGFLOW_FALLBACK_TO_ENV_VAR` | Boolean | `true` | If enabled, [global variables](../Configuration/configuration-global-variables.md) set in the Langflow UI fall back to an environment variable with the same name when Langflow fails to retrieve the variable value. |
| <Link id="LANGFLOW_FRONTEND_PATH"/>`LANGFLOW_FRONTEND_PATH` | String | `./frontend` | Path to the frontend directory containing build files. This is for development purposes only.<br/>See [`--frontend-path` option](./configuration-cli.md#run-frontend-path). |
| <Link id="LANGFLOW_HEALTH_CHECK_MAX_RETRIES"/>`LANGFLOW_HEALTH_CHECK_MAX_RETRIES` | Integer | `5` | Set the maximum number of retries for the health check.<br/>See [`--health-check-max-retries` option](./configuration-cli.md#run-health-check-max-retries). |
| <Link id="LANGFLOW_HOST"/>`LANGFLOW_HOST` | String | `127.0.0.1` | The host on which the Langflow server will run.<br/>See [`--host` option](./configuration-cli.md#run-host). |
| <Link id="LANGFLOW_LANGCHAIN_CACHE"/>`LANGFLOW_LANGCHAIN_CACHE` | `InMemoryCache`<br/>`SQLiteCache` | `InMemoryCache` | Type of cache to use.<br/>See [`--cache` option](./configuration-cli.md#run-cache). |
| <Link id="LANGFLOW_LOG_LEVEL"/>`LANGFLOW_LOG_LEVEL` | `DEBUG`<br/>`INFO`<br/>`WARNING`<br/>`ERROR`<br/>`CRITICAL` | `INFO` | Set the logging level for Langflow. |
| <Link id="LANGFLOW_LOG_FILE"/>`LANGFLOW_LOG_FILE` | String | Not set | Path to the log file. If not set, logs will be written to stdout. |
| <Link id="LANGFLOW_MAX_FILE_SIZE_UPLOAD"/>`LANGFLOW_MAX_FILE_SIZE_UPLOAD` | Integer | `100` | Set the maximum file size for the upload in megabytes.<br/>See [`--max-file-size-upload` option](./configuration-cli.md#run-max-file-size-upload). |
| <Link id="LANGFLOW_MCP_SERVER_ENABLED"/>`LANGFLOW_MCP_SERVER_ENABLED` | Boolean | `true` | If set to False, Langflow will not enable the MCP server. |
| <Link id="LANGFLOW_MCP_SERVER_ENABLE_PROGRESS_NOTIFICATIONS"/>`LANGFLOW_MCP_SERVER_ENABLE_PROGRESS_NOTIFICATIONS` | Boolean | `false` | If set to True, Langflow will send progress notifications in the MCP server. |
| <Link id="LANGFLOW_NEW_USER_IS_ACTIVE"/>`LANGFLOW_NEW_USER_IS_ACTIVE` | Boolean | `false` | When enabled, new users are automatically activated and can log in without requiring explicit activation by the superuser. |
| <Link id="LANGFLOW_OPEN_BROWSER"/>`LANGFLOW_OPEN_BROWSER` | Boolean | `false` | Open the system web browser on startup.<br/>See [`--open-browser` option](./configuration-cli.md#run-open-browser). |
| <Link id="LANGFLOW_PORT"/>`LANGFLOW_PORT` | Integer | `7860` | The port on which the Langflow server will run. The server automatically selects a free port if the specified port is in use.<br/>See [`--port` option](./configuration-cli.md#run-port). |
| <Link id="LANGFLOW_PROMETHEUS_ENABLED"/>`LANGFLOW_PROMETHEUS_ENABLED` | Boolean | `false` | Expose Prometheus metrics. |
| <Link id="LANGFLOW_PROMETHEUS_PORT"/>`LANGFLOW_PROMETHEUS_PORT` | Integer | `9090` | Set the port on which Langflow exposes Prometheus metrics. |
| <Link id="LANGFLOW_REDIS_CACHE_EXPIRE"/>`LANGFLOW_REDIS_CACHE_EXPIRE` | Integer | `3600` | See [`LANGFLOW_CACHE_TYPE`](#LANGFLOW_CACHE_TYPE). |
| <Link id="LANGFLOW_REDIS_DB"/>`LANGFLOW_REDIS_DB` | Integer | `0` | See [`LANGFLOW_CACHE_TYPE`](#LANGFLOW_CACHE_TYPE). |
| <Link id="LANGFLOW_REDIS_HOST"/>`LANGFLOW_REDIS_HOST` | String | `localhost` | See [`LANGFLOW_CACHE_TYPE`](#LANGFLOW_CACHE_TYPE). |
| <Link id="LANGFLOW_REDIS_PORT"/>`LANGFLOW_REDIS_PORT` | String | `6379` | See [`LANGFLOW_CACHE_TYPE`](#LANGFLOW_CACHE_TYPE). |
| <Link id="LANGFLOW_REMOVE_API_KEYS"/>`LANGFLOW_REMOVE_API_KEYS` | Boolean | `false` | Remove API keys from the projects saved in the database.<br/>See [`--remove-api-keys` option](./configuration-cli.md#run-remove-api-keys). |
| <Link id="LANGFLOW_SAVE_DB_IN_CONFIG_DIR"/>`LANGFLOW_SAVE_DB_IN_CONFIG_DIR` | Boolean | `false` | Save the Langflow database in [`LANGFLOW_CONFIG_DIR`](#LANGFLOW_CONFIG_DIR) instead of in the Langflow package directory. Note, when this variable is set to default (`false`), the database isn't shared between different virtual environments and the database is deleted when you uninstall Langflow. |
| <Link id="LANGFLOW_SECRET_KEY"/>`LANGFLOW_SECRET_KEY` | String | Auto-generated | Key used for encrypting sensitive data like API keys. If not provided, a secure key will be auto-generated. For production environments with multiple instances, you should explicitly set this to ensure consistent encryption across instances. |
| <Link id="LANGFLOW_STORE"/>`LANGFLOW_STORE` | Boolean | `true` | Enable the Langflow Store.<br/>See [`--store` option](./configuration-cli.md#run-store). |
| <Link id="LANGFLOW_STORE_ENVIRONMENT_VARIABLES"/>`LANGFLOW_STORE_ENVIRONMENT_VARIABLES` | Boolean | `true` | Store environment variables as [global variables](../Configuration/configuration-global-variables.md) in the database. |
| <Link id="LANGFLOW_SUPERUSER"/>`LANGFLOW_SUPERUSER` | String | `langflow` | Set the name for the superuser. Required if [`LANGFLOW_AUTO_LOGIN`](#LANGFLOW_AUTO_LOGIN) is set to `false`.<br/>See [`superuser --username` option](./configuration-cli.md#superuser-username). |
| <Link id="LANGFLOW_SUPERUSER_PASSWORD"/>`LANGFLOW_SUPERUSER_PASSWORD` | String | `langflow` | Set the password for the superuser. Required if [`LANGFLOW_AUTO_LOGIN`](#LANGFLOW_AUTO_LOGIN) is set to `false`.<br/>See [`superuser --password` option](./configuration-cli.md#superuser-password). |
| <Link id="LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT"/>`LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` | String | Not set | Comma-separated list of environment variables to get from the environment and store as [global variables](../Configuration/configuration-global-variables.md). |
| <Link id="LANGFLOW_LOAD_FLOWS_PATH"/>`LANGFLOW_LOAD_FLOWS_PATH` | String | Not set | Path to a directory containing flow JSON files to be loaded on startup. Note that this feature only works if `LANGFLOW_AUTO_LOGIN` is enabled. |
| <Link id="LANGFLOW_WORKER_TIMEOUT"/>`LANGFLOW_WORKER_TIMEOUT` | Integer | `300` | Worker timeout in seconds.<br/>See [`--worker-timeout` option](./configuration-cli.md#run-worker-timeout). |
| <Link id="LANGFLOW_WORKERS"/>`LANGFLOW_WORKERS` | Integer | `1` | Number of worker processes.<br/>See [`--workers` option](./configuration-cli.md#run-workers). |
