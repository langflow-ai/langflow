---
title: Install Langflow
slug: /get-started-installation
---

You can deploy Langflow either locally or as a hosted service with [**Datastax Langflow**](#datastax-langflow).

## Install Langflow locally

Install Langflow locally with [uv (recommended)](https://docs.astral.sh/uv/getting-started/installation/), [pip](https://pypi.org/project/pip/), or [pipx](https://pipx.pypa.io/stable/installation/).

### Prerequisites

- [Python 3.10 to 3.12](https://www.python.org/downloads/release/python-3100/) installed
- [uv](https://docs.astral.sh/uv/getting-started/installation/), [pip](https://pypi.org/project/pip/), or [pipx](https://pipx.pypa.io/stable/installation/) installed
- Before installing Langflow, we recommend creating a virtual environment to isolate your Python dependencies with [uv](https://docs.astral.sh/uv/pip/environments), [venv](https://docs.python.org/3/library/venv.html), or [conda](https://anaconda.org/anaconda/conda)

### Install Langflow with pip or pipx

Install Langflow with uv:

```bash
uv pip install langflow
```

Install Langflow with pip:

```bash
python -m pip install langflow
```

Install Langflow with pipx using the Python 3.10 executable:

```bash
pipx install langflow --python python3.10
```

## Run Langflow

1. To run Langflow with uv, enter the following command.

```bash
uv run langflow run
```

2. To run Langflow with pip, enter the following command.

```bash
python -m langflow run
```

3. Confirm that a local Langflow instance starts by visiting `http://127.0.0.1:7860` in a Chromium-based browser.

Now that Langflow is running, follow the [Quickstart](/get-started-quickstart) to create your first flow.

## Manage Langflow versions

To upgrade Langflow to the latest version with uv, use the uv pip upgrade command.

```bash
uv pip install langflow -U
```

To upgrade Langflow to the latest version, use the pip upgrade command.

```bash
python -m pip install langflow -U
```

To install a specific version of the Langflow package, add the required version to the command.

```bash
python -m pip install langflow==1.1
```

To reinstall Langflow and all of its dependencies, add the `--force-reinstall` flag to the command.

```bash
python -m pip install langflow --force-reinstall
```

## DataStax Langflow {#datastax-langflow}

**DataStax Langflow** is a hosted version of Langflow integrated with [Astra DB](https://www.datastax.com/products/datastax-astra). Be up and running in minutes with no installation or setup required. [Sign up for free](https://astra.datastax.com/signup?type=langflow).

## Common installation issues

This is a list of possible issues that you may encounter when installing and running Langflow.

### No `langflow.__main__` module

When you try to run Langflow with the command `langflow run`, you encounter the following error:

```bash
> No module named 'langflow.__main__'
```

1. Run `python -m langflow run` instead of `langflow run`.
2. If that doesn't work, reinstall the latest Langflow version with `python -m pip install langflow -U`.
3. If that doesn't work, reinstall Langflow and its dependencies with `python -m pip install langflow --pre -U --force-reinstall`.

### Langflow runTraceback

When you try to run Langflow using the command `langflow run`, you encounter the following error:

```bash
> langflow runTraceback (most recent call last): File ".../langflow", line 5, in <module>  from langflow.__main__ import mainModuleNotFoundError: No module named 'langflow.__main__'
```

There are two possible reasons for this error:

1. You've installed Langflow using `pip install langflow` but you already had a previous version of Langflow installed in your system. In this case, you might be running the wrong executable. To solve this issue, run the correct executable by running `python -m langflow run` instead of `langflow run`. If that doesn't work, try uninstalling and reinstalling Langflow with `python -m pip install langflow --pre -U`.
2. Some version conflicts might have occurred during the installation process. Run `python -m pip install langflow --pre -U --force-reinstall` to reinstall Langflow and its dependencies.

### Something went wrong running migrations

```bash
> Something went wrong running migrations. Please, run 'langflow migration --fix'
```

Clear the cache by deleting the contents of the cache folder.

This folder can be found at:

- **Linux or WSL2 on Windows**: `home/<username>/.cache/langflow/`
- **MacOS**: `/Users/<username>/Library/Caches/langflow/`

This error can occur during Langflow upgrades when the new version can't override `langflow-pre.db` in `.cache/langflow/`. Clearing the cache removes this file but also erases your settings.

If you wish to retain your files, back them up before clearing the folder.

### Langflow installation freezes at pip dependency resolution

Installing Langflow with `pip install langflow` slowly fails with this error message:

```plain
pip is looking at multiple versions of <<library>> to determine which version is compatible with other requirements. This could take a while.
```

To work around this issue, install Langflow with [`uv`](https://docs.astral.sh/uv/getting-started/installation/) instead of `pip`.

```plain
uv pip install langflow
```

To run Langflow with uv:

```plain
uv run langflow run
```
