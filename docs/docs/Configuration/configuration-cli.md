---
title: Langflow CLI
slug: /configuration-cli
---

import Link from '@docusaurus/Link';

# Langflow CLI

The Langflow command line interface (Langflow CLI) is the main interface for managing and running the Langflow server.

## CLI commands

The following sections describe the available CLI commands and their options, as well as their corresponding [environment variables](./environment-variables.md).

### langflow

Running the CLI without any arguments displays a list of available options and commands.

```bash
langflow [OPTIONS]
# or
python -m langflow [OPTIONS]
```

#### Options

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| <Link id="install-completion"/>`--install-completion` | *Not applicable* | *Not applicable* | Install auto-completion for the current shell. |
| <Link id="show-completion"/>`--show-completion` | *Not applicable* | *Not applicable* | Show the location of the auto-completion config file, if installed. |
| <Link id="help"/>`--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

### langflow api-key

Create an API key for the default superuser if the `LANGFLOW_AUTO_LOGIN` environment variable is set to `true`.

```bash
langflow api-key [OPTIONS]
# or
python -m langflow api-key [OPTIONS]
```

#### Options

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| <Link id="install-completion"/>`--install-completion` | *Not applicable* | *Not applicable* | Install auto-completion for the current shell. |
| <Link id="show-completion"/>`--show-completion` | *Not applicable* | *Not applicable* | Show the location of the auto-completion config file (if installed). |
| <Link id="help"/>`--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

### langflow copy-db

Copy the database files to the current directory.
Copy the Langflow database files, `langflow.db` and `langflow-pre.db` (if they exist), from the cache directory to the current directory.

:::note
The current directory is the directory containing `__main__.py`.
You can find this directory by running `which langflow`.
:::

```bash
langflow copy-db
# or
python -m langflow copy-db
```

#### Options

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| <Link id="copy-db-help"/>`--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

### langflow migration

Run or test database migrations.

```bash
langflow migration [OPTIONS]
# or
python -m langflow migration [OPTIONS]
```

#### Options

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| <Link id="migration-test"/>`--test` | `true` | Boolean | Run migrations in test mode. Use `--no-test` to disable test mode. |
| <Link id="migration-fix"/>`--fix` | `false` (`--no-fix`) | Boolean | Fix migrations. This is a destructive operation, and all affected data will be deleted. Only use this option if you know what you are doing. |
| <Link id="migration-help"/>`--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

### langflow run

Start the Langflow server.

```bash
langflow run [OPTIONS]
# or
python -m langflow run [OPTIONS]
```

#### Options

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| <Link id="run-host"/>`--host` | `localhost` | String | The host on which the Langflow server will run.<br/>See [`LANGFLOW_HOST` variable](./environment-variables.md#LANGFLOW_HOST). |
| <Link id="run-workers"/>`--workers` | `1` | Integer | Number of worker processes.<br/>See [`LANGFLOW_WORKERS` variable](./environment-variables.md#LANGFLOW_WORKERS). |
| <Link id="run-worker-timeout"/>`--worker-timeout` | `300` | Integer | Worker timeout in seconds.<br/>See [`LANGFLOW_WORKER_TIMEOUT` variable](./environment-variables.md#LANGFLOW_WORKER_TIMEOUT). |
| <Link id="run-port"/>`--port` | `7860` | Integer | The port on which the Langflow server will run. The server automatically selects a free port if the specified port is in use.<br/>See [`LANGFLOW_PORT` variable](./environment-variables.md#LANGFLOW_PORT). |
| <Link id="run-components-path"/>`--components-path` | `langflow/components` | String | Path to the directory containing custom components.<br/>See [`LANGFLOW_COMPONENTS_PATH` variable](./environment-variables.md#LANGFLOW_COMPONENTS_PATH). |
| <Link id="run-env-file"/>`--env-file` | Not set | String | Path to the `.env` file containing environment variables.<br/>See [Import environment variables from a .env file](./environment-variables.md#configure-variables-env-file). |
| <Link id="run-log-level"/>`--log-level` | `critical` | `debug`<br/>`info`<br/>`warning`<br/>`error`<br/>`critical` | Set the logging level.<br/>See [`LANGFLOW_LOG_LEVEL` variable](./environment-variables.md#LANGFLOW_LOG_LEVEL). |
| <Link id="run-log-file"/>`--log-file` | `logs/langflow.log` | String | Set the path to the log file for Langflow.<br/>See [`LANGFLOW_LOG_FILE` variable](./environment-variables.md#LANGFLOW_LOG_FILE). |
| <Link id="run-cache"/>`--cache` | `async` | `async`<br/>`redis`<br/>`memory`<br/>`disk` | Type of cache to use.<br/>See [`LANGFLOW_CACHE_TYPE` variable](./environment-variables.md#LANGFLOW_CACHE_TYPE). |
| <Link id="run-frontend-path"/>`--frontend-path` | `./frontend` | String | Path to the frontend directory containing build files. This is for development purposes only.<br/>See [`LANGFLOW_FRONTEND_PATH` variable](./environment-variables.md#LANGFLOW_FRONTEND_PATH). |
| <Link id="run-open-browser"/>`--open-browser` | `true` | Boolean | Open the system web browser on startup. Use `--no-open-browser` to disable opening the system web browser on startup.<br/> See [`LANGFLOW_OPEN_BROWSER` variable](./environment-variables.md#LANGFLOW_OPEN_BROWSER). |
| <Link id="run-remove-api-keys"/>`--remove-api-keys` | `false` (`--no-remove-api-keys`) | Boolean | Remove API keys from the projects saved in the database.<br/> See [`LANGFLOW_REMOVE_API_KEYS` variable](./environment-variables.md#LANGFLOW_REMOVE_API_KEYS). |
| <Link id="run-backend-only"/>`--backend-only` | `false` (`--no-backend-only`) | Boolean | Only run Langflow's backend server (no frontend).<br/>See [`LANGFLOW_BACKEND_ONLY` variable](./environment-variables.md#LANGFLOW_BACKEND_ONLY). |
| <Link id="run-store"/>`--store` | `true` | Boolean | Enable the Langflow Store features. Use `--no-store` to disable the Langflow Store features.<br/>See [`LANGFLOW_STORE` variable](./environment-variables.md#LANGFLOW_STORE). |
| <Link id="run-auto-saving"/>`--auto-saving` | `true` | Boolean | Enable flow auto-saving. Use `--no-auto-saving` to disable flow auto-saving.<br/>See [`LANGFLOW_AUTO_SAVING` variable](./environment-variables.md#LANGFLOW_AUTO_SAVING). |
| <Link id="run-auto-saving-interval"/>`--auto-saving-interval` | `1000` | Integer | Set the interval for flow auto-saving in milliseconds.<br/>See [`LANGFLOW_AUTO_SAVING_INTERVAL` variable](./environment-variables.md#LANGFLOW_AUTO_SAVING_INTERVAL). |
| <Link id="run-health-check-max-retries"/>`--health-check-max-retries` | `5` | Integer | Set the maximum number of retries for the health check. Use `--no-health-check-max-retries` to disable the maximum number of retries for the health check.<br/>See [`LANGFLOW_HEALTH_CHECK_MAX_RETRIES` variable](./environment-variables.md#LANGFLOW_HEALTH_CHECK_MAX_RETRIES). |
| <Link id="run-max-file-size-upload"/>`--max-file-size-upload` | `100` | Integer | Set the maximum file size for the upload in megabytes.<br/>See [`LANGFLOW_MAX_FILE_SIZE_UPLOAD` variable](./environment-variables.md#LANGFLOW_MAX_FILE_SIZE_UPLOAD). |
| <Link id="run-ssl-cert-file-path"/>`--ssl-cert-file-path` | Not set | String | Path to the SSL certificate file on the local system. |
| <Link id="run-ssl-key-file-path"/>`--ssl-key-file-path` | Not set | String | Path to the SSL key file on the local system. |
| <Link id="run-help"/>`--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

### langflow superuser

Create a superuser account.

```bash
langflow superuser [OPTIONS]
# or
python -m langflow superuser [OPTIONS]
```

#### Options

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| <Link id="superuser-username"/>`--username` | Required | String | Specify the name for the superuser.<br/>See [`LANGFLOW_SUPERUSER` variable](./environment-variables.md#LANGFLOW_SUPERUSER). |
| <Link id="superuser-password"/>`--password` | Required | String | Specify the password for the superuser.<br/>See [`LANGFLOW_SUPERUSER_PASSWORD` variable](./environment-variables.md#LANGFLOW_SUPERUSER_PASSWORD). |

## Precedence

Langflow CLI options override the values of corresponding [environment variables](./environment-variables.md).

For example, if you have `LANGFLOW_PORT=7860` defined as an environment variable, but you run the CLI with `--port 7880`, Langflow sets the port to **`7880`**, the value passed with the CLI.

## Assign values

There are two ways you can assign a value to a CLI option.
You can write the option flag and its value with a single space between them: `--option value`.
Or, you can write them using an equals sign (`=`) between the option flag and the value: `--option=value`.

Values that contain spaces must be surrounded by quotation marks: `--option 'Value with Spaces'` or `--option='Value with Spaces'`.

### Boolean values {#boolean}

Boolean options turn a behavior on or off, and therefore accept no arguments.
To activate a boolean option, type it on the command line.
For example:

```bash
langflow run --remove-api-keys
```

All boolean options have a corresponding option that negates it.
For example, the negating option for `--remove-api-keys` is `--no-remove-api-keys`.
These options let you negate boolean options that you may have set using [environment variables](./environment-variables.md).
