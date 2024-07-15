---
title: Command Line Interface (CLI)
sidebar_position: 2
slug: /configuration-cli
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




Langflow's Command Line Interface (CLI) is a powerful tool that allows you to interact with the Langflow server from the command line. The CLI provides a wide range of commands to help you shape Langflow to your needs.


The available commands are below. Navigate to their individual sections of this page to see the parameters.

- [langflow](/configuration-cli)
- [langflow api-key](/configuration-cli)
- [langflow copy-db](/configuration-cli)
- [langflow migration](/configuration-cli)
- [langflow run](/configuration-cli)
- [langflow superuser](/configuration-cli)

## Overview {#c50e5530289349cf8ed7bee22ba2211a}


Running the CLI without any arguments displays a list of available options and commands.


```shell
langflow
# or
langflow --help
# or
python -m langflow

```


| Command     | Description                                                            |
| ----------- | ---------------------------------------------------------------------- |
| `api-key`   | Creates an API key for the default superuser if AUTO_LOGIN is enabled. |
| `copy-db`   | Copy the database files to the current directory (`which langflow`).   |
| `migration` | Run or test migrations.                                                |
| `run`       | Run the Langflow.                                                      |
| `superuser` | Create a superuser.                                                    |


### Options {#8a3b5b7ed55b4774ad6d533bb337ef47}


| Option                 | Description                                                                      |
| ---------------------- | -------------------------------------------------------------------------------- |
| `--install-completion` | Install completion for the current shell.                                        |
| `--show-completion`    | Show completion for the current shell, to copy it or customize the installation. |
| `--help`               | Show this message and exit.                                                      |


## langflow api-key {#dbfc8c4c83474b83a38bdc7471bccf41}


Run the `api-key` command to create an API key for the default superuser if `LANGFLOW_AUTO_LOGIN` is set to `True`.


```shell
langflow api-key
# or
python -m langflow api-key
╭─────────────────────────────────────────────────────────────────────╮
│ API Key Created Successfully:                                       │
│                                                                     │
│ sk-O0elzoWID1izAH8RUKrnnvyyMwIzHi2Wk-uXWoNJ2Ro                      │
│                                                                     │
│ This is the only time the API key will be displayed.                │
│ Make sure to store it in a secure location.                         │
│                                                                     │
│ The API key has been copied to your clipboard. Cmd + V to paste it. │
╰──────────────────────────────

```


### Options {#ec2ef993dc984811b25838c8d8230b31}


| Option      | Type | Description                                                   |
| ----------- | ---- | ------------------------------------------------------------- |
| --log-level | TEXT | Logging level. [env var: LANGFLOW_LOG_LEVEL] [default: error] |
| --help      |      | Show this message and exit.                                   |


## langflow copy-db {#729a13f4847545e5973d8f9c20f8833d}


Run the `copy-db` command to copy the cached `langflow.db` and `langflow-pre.db` database files to the current directory.


If the files exist in the cache directory, they will be copied to the same directory as `__main__.py`, which can be found with `which langflow`.


### Options {#7b7e6bd02b3243218e1d666711854673}


None.


## langflow migration {#7027c1925a444119a7a8ea2bff4bd16d}


Run or test migrations with the Alembic database tool.


```shell
langflow migration
# or
python -m langflow migration

```


### Options {#0b38fbe97bb34edeb7740a7db58433e9}


| Option              | Description                                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `--test, --no-test` | Run migrations in test mode. [default: test]                                                                               |
| `--fix, --no-fix`   | Fix migrations. This is a destructive operation, and should only be used if you know what you are doing. [default: no-fix] |
| `--help`            | Show this message and exit.                                                                                                |


## langflow run {#fe050aa659cb4d33a560b859d54c94ea}


Run Langflow.


```shell
langflow run
# or
python -m langflow run

```


### Options {#4e811481ec9142f1b60309bb1ce5a2ce}


| Option                                                     | Description                                                                                                                                                                               |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--help`                                                   | Displays all available options.                                                                                                                                                           |
| `--host`                                                   | Defines the host to bind the server to. Can be set using the `LANGFLOW_HOST` environment variable. The default is `127.0.0.1`.                                                            |
| `--workers`                                                | Sets the number of worker processes. Can be set using the `LANGFLOW_WORKERS` environment variable. The default is `1`.                                                                    |
| `--timeout`                                                | Sets the worker timeout in seconds. The default is `60`.                                                                                                                                  |
| `--port`                                                   | Sets the port to listen on. Can be set using the `LANGFLOW_PORT` environment variable. The default is `7860`.                                                                             |
| `--env-file`                                               | Specifies the path to the .env file containing environment variables. The default is `.env`.                                                                                              |
| `--log-level`                                              | Defines the logging level. Can be set using the `LANGFLOW_LOG_LEVEL` environment variable. The default is `critical`.                                                                     |
| `--components-path`                                        | Specifies the path to the directory containing custom components. Can be set using the `LANGFLOW_COMPONENTS_PATH` environment variable. The default is `langflow/components`.             |
| `--log-file`                                               | Specifies the path to the log file. Can be set using the `LANGFLOW_LOG_FILE` environment variable. The default is `logs/langflow.log`.                                                    |
| `--cache`                                                  | Select the type of cache to use. Options are `InMemoryCache` and `SQLiteCache`. Can be set using the `LANGFLOW_LANGCHAIN_CACHE` environment variable. The default is `SQLiteCache`.       |
| `--dev`/`--no-dev`                                         | Toggles the development mode. The default is `no-dev`.                                                                                                                                    |
| `--path`                                                   | Specifies the path to the frontend directory containing build files. This option is for development purposes only. Can be set using the `LANGFLOW_FRONTEND_PATH` environment variable.    |
| `--open-browser`/`--no-open-browser`                       | Toggles the option to open the browser after starting the server. Can be set using the `LANGFLOW_OPEN_BROWSER` environment variable. The default is `open-browser`.                       |
| `--remove-api-keys`/`--no-remove-api-keys`                 | Toggles the option to remove API keys from the projects saved in the database. Can be set using the `LANGFLOW_REMOVE_API_KEYS` environment variable. The default is `no-remove-api-keys`. |
| `--install-completion [bash\|zsh\|fish\|powershell\|pwsh]` | Installs completion for the specified shell.                                                                                                                                              |
| `--show-completion [bash\|zsh\|fish\|powershell\|pwsh]`    | Shows completion for the specified shell, allowing you to copy it or customize the installation.                                                                                          |
| `--backend-only`                                           | This parameter, with a default value of `False`, allows running only the backend server without the frontend. It can also be set using the `LANGFLOW_BACKEND_ONLY` environment variable.  |
| `--store`                                                  | This parameter, with a default value of `True`, enables the store features, use `--no-store` to deactivate it. It can be configured using the `LANGFLOW_STORE` environment variable.      |


### CLI environment variables {#5868aaccfcc74e26968538ef4d07e756}


You can configure many of the CLI options using environment variables. These can be exported in your operating system or added to a `.env` file and loaded using the `--env-file` option.


A sample `.env` file named `.env.example` is included with the project. Copy this file to a new file named `.env` and replace the example values with your actual settings. If you're setting values in both your OS and the `.env` file, the `.env` settings will take precedence.


## langflow superuser {#5944233ce0c942878e928e1f2945d717}


Create a superuser for Langflow.


```shell
langflow superuser
# or
python -m langflow superuser
```


### Options {#f333c5635ead4c3d95985467bb08cc8f}


| Option        | Type | Description                                                   |
| ------------- | ---- | ------------------------------------------------------------- |
| `--username`  | TEXT | Username for the superuser. [default: None] [required]        |
| `--password`  | TEXT | Password for the superuser. [default: None] [required]        |
| `--log-level` | TEXT | Logging level. [env var: LANGFLOW_LOG_LEVEL] [default: error] |
| `--help`      |      | Show this message and exit.                                   |

