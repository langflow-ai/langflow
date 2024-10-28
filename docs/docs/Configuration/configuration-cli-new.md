---
title: CLI Reference (NEW)
sidebar_position: 7
slug: /configuration-cli-new
---

# Langflow CLI Reference

The Langflow command line interface (Langflow CLI) is the main interface for managing and running the Langflow server.

## Commands reference

The following sections list the available CLI commands and their options, as well as any corresponding [environment variables](./environment-variables.md).

### langflow

Running the CLI without any arguments displays a list of available options and commands.

```bash
langflow [OPTIONS]
# or
python -m langflow [OPTIONS]
```

#### Options

| Option | Default | Values | Description |
|--------|------|-----------|-------------|
| `--install-completion` | *Not applicable* | *Not applicable* | Install auto-completion for the current shell. |
| `--show-completion` | *Not applicable* | *Not applicable* | Show the location of the auto-completion config file ( if installed). |
| `--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

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
| `--log-level` | `critical` | `debug`<br/>`info`<br/>`warning`<br/>`error`<br/>`critical` | Specify the logging level. Can also be set using the `LANGFLOW_LOG_LEVEL` environment variable. |
| `--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

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
| `--help` | *Not applicable* | *Not applicable* | Display information about the command usage and its options and arguments. |

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
| `--test` | `true` | BOOLEAN | Run migrations in test mode. Use `--no-test` to disable test mode. |
| `--fix` | `false` (`--no-fix`) | BOOLEAN | Fix migrations. This is a destructive operation, and all affected data will be deleted. Only use this option if you know what you are doing. |
| `--help` | *Not applicable* | *Not applicable* | Displays information about the command usage and its options and arguments. |


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
| `--host` | `127.0.0.1` | TEXT | Host to bind the server to. Can also be set using the `LANGFLOW_HOST` environment variable. |
| `--workers` | `1` | INTEGER | Number of worker processes. Can also be set using the `LANGFLOW_WORKERS` environment variable. |
| `--worker-timeout` | `60` | INTEGER | Worker timeout in seconds. |
| `--port` | `7860` | INTEGER | Port to listen on. Can also be set using the `LANGFLOW_PORT` environment variable. Note, the server automatically selects a free port if the specified port is in use. |
| `--components-path` | `./components` | PATH | Path to the directory containing custom components. Can also be set using the `LANGFLOW_COMPONENTS_PATH` environment variable. |
| `--env-file` | Not set | PATH | Path to the `.env` file containing environment variables.<br/> See [Import environment variables from a .env file](./environment-variables.md#configure-variables-env-file). |
| `--log-level` | `critical` | `debug`<br/>`info`<br/>`warning`<br/>`error`<br/>`critical` | Specify the logging level. Can also be set using the `LANGFLOW_LOG_LEVEL` environment variable. |
| `--log-file` | `logs/langflow.log` | PATH | Path to the log file. Can also be set using the `LANGFLOW_LOG_FILE` environment variable. |
| `--cache` | `SQLiteCache` | `InMemoryCache`<br/>`SQLiteCache` | Type of cache to use. Can also be set using the `LANGFLOW_LANGCHAIN_CACHE` environment variable. |
| `--dev` | `false` (`--no-dev`) | BOOLEAN | Run in development mode (may contain bugs). |
| `--frontend-path` | `./frontend` | TEXT | Path to the frontend directory containing build files. This is for development purposes only. Can also be set using the `LANGFLOW_FRONTEND_PATH` environment variable. |
| `--open-browser` | `true` | BOOLEAN | Open the browser after starting the server. Can also be set using the `LANGFLOW_OPEN_BROWSER` environment variable. Use `--no-open-browser` to disable opening the browser after starting the server. |
| `--remove-api-keys` | `false` (`--no-remove-api-keys`) | BOOLEAN | Remove API keys from the projects saved in the database. Can also be set using the `LANGFLOW_REMOVE_API_KEYS` environment variable. |
| `--backend-only` | `false` (`--no-backend-only`) | BOOLEAN | Run only the backend server without the frontend. Can also be set using the `LANGFLOW_BACKEND_ONLY` environment variable. |
| `--store` | `true` | BOOLEAN | Enables the store features. Use `--no-store` to disable the store features. Can also be set using the `LANGFLOW_STORE` environment variable.|
| `--auto-saving` | `true` | BOOLEAN | Defines if the auto save is enabled. Use `--no-auto-saving` to disable auto save. Can also be set using the `LANGFLOW_AUTO_SAVING` environment variable.|
| `--auto-saving-interval` | None | INTEGER | Defines the debounce time for the auto save in seconds. |
| `--health-check-max-retries` | None | INTEGER | Defines the number of retries for the health check. Use `--no-health-check-max-retries` to disable the maximum number of retries. |
| `--max-file-size-upload` | None | INTEGER | Defines the maximum file size for the upload in MB. |
| `--help` | *Not applicable* | *Not applicable* | Displays information about the command usage and its options and arguments. |

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
| `--username` | Required | TEXT | Specify the name for the superuser. |
| `--password` | Required | TEXT | Specify the password for the superuser. |
| `--log-level` | `critical` | `debug`<br/>`info`<br/>`warning`<br/>`error`<br/>`critical` | Specify the logging level. Can also be set using the `LANGFLOW_LOG_LEVEL` environment variable. |

## Precedence

Langflow CLI options override the values of corresponding [environment variables](./environment-variables.md).

For example, if you have `LANGFLOW_PORT=7860` defined as an environment variable, but you run the CLI with `--port 7880`, then Langflow will set the port to **`7880`** (the value passed with the CLI).

## Value types

There are two ways you can assign a value to a CLI option.
You can write the option flag and its value with a single space between them: `--option value`.
Or, you can write them using an equals sign (`=`) between the option flag and the value: `--option=value`.

Values that contain spaces must be surrounded by quotation marks: `--option 'Value with Spaces'` or `--option='Value with Spaces'`.

## Boolean values

Boolean options turn a behavior on or off, and therefore accept no arguments.
To activate a boolean option, type it on the command line:

```bash
langflow run --remove-api-keys
```

All boolean options have a corresponding option that negates it.
For example, the negating option for `--remove-api-keys` is `--no-remove-api-keys`.
These options let you negate boolean options that you may have defined as [environment variables](./environment-variables.md).
