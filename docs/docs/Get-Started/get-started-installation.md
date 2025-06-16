---
title: Install Langflow
slug: /get-started-installation
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow can be installed in three ways:

* As a [Python package](#install-and-run-langflow-oss) with Langflow OSS
* As a [standalone desktop application](#install-and-run-langflow-desktop) with Langflow Desktop
* As a [cloud-hosted service](#datastax-langflow) with DataStax Langflow

## Install and run Langflow OSS

Before you install and run Langflow OSS, be sure you have the following items.

- [Python 3.10 to 3.13](https://www.python.org/downloads/release/python-3100/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) or [pip](https://pypi.org/project/pip/)
- A virtual environment created with [uv](https://docs.astral.sh/uv/pip/environments) or [venv](https://docs.python.org/3/library/venv.html)
- A dual-core CPU and at least 2 GB of RAM. More intensive use requires a multi-core CPU and at least 4 GB of RAM.

Install and run Langflow OSS with [uv (recommended)](https://docs.astral.sh/uv/getting-started/installation/) or [pip](https://pypi.org/project/pip/).

1. To install Langflow, use one of the following commands:

<Tabs groupId="package-manager">
<TabItem value="uv" label="uv" default>

```bash
uv pip install langflow
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
pip install langflow
```

</TabItem>
</Tabs>

2. To run Langflow, use one of the following commands:

<Tabs groupId="package-manager">
    <TabItem value="uv" label="uv">

```bash
uv run langflow run
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
python -m langflow run
```

</TabItem>
</Tabs>

3. To confirm that a local Langflow instance starts, go to the default Langflow URL at `http://localhost:7860`.

After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

### Manage Langflow OSS versions

To upgrade Langflow to the latest version, use one of the following commands:

<Tabs groupId="package-manager">
<TabItem value="uv" label="uv" default>

```bash
uv pip install langflow -U
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
pip install langflow -U
```

</TabItem>
</Tabs>

To install a specific version of the Langflow package, add the required version to the command.
<Tabs groupId="package-manager">
<TabItem value="uv" label="uv" default>

```bash
uv pip install langflow==1.3.2
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
pip install langflow==1.3.2
```

</TabItem>
</Tabs>

To reinstall Langflow and all of its dependencies, add the `--force-reinstall` flag to the command.
<Tabs groupId="package-manager">
<TabItem value="uv" label="uv" default>

```bash
uv pip install langflow --force-reinstall
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
pip install langflow --force-reinstall
```

</TabItem>
</Tabs>

### Install optional dependencies for Langflow OSS

Langflow OSS provides optional dependency groups that extend its functionality.

These dependencies are listed in the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L191) file under `[project.optional-dependencies]`.

Install dependency groups using pip's `[extras]` syntax. For example, to install Langflow with the `postgresql` dependency group, enter one of the following commands:

<Tabs groupId="package-manager">
<TabItem value="uv" label="uv" default>

```bash
uv pip install "langflow[postgresql]"
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
pip install "langflow[postgresql]"
```

</TabItem>
</Tabs>

To install multiple extras, enter one of the following commands:

<Tabs groupId="package-manager">
<TabItem value="uv" label="uv" default>

```bash
uv pip install "langflow[deploy,local,postgresql]"
```

</TabItem>
<TabItem value="pip" label="pip">

```bash
pip install "langflow[deploy,local,postgresql]"
```

</TabItem>
</Tabs>

To add your own custom dependencies, see [Install custom dependencies](/install-custom-dependencies).

### Stop Langflow OSS

To stop Langflow, in the terminal where it's running, enter `Ctrl+C`.

To deactivate your virtual environment, enter `deactivate`.

### Common OSS installation issues

This is a list of possible issues that you may encounter when installing and running Langflow.

#### No `langflow.__main__` module

When you try to run Langflow with the command `langflow run`, you encounter the following error:

```bash
> No module named 'langflow.__main__'
```

1. Run `uv run langflow run` instead of `langflow run`.
2. If that doesn't work, reinstall the latest Langflow version with `uv pip install langflow -U`.
3. If that doesn't work, reinstall Langflow and its dependencies with `uv pip install langflow --pre -U --force-reinstall`.

#### Langflow runTraceback

When you try to run Langflow using the command `langflow run`, you encounter the following error:

```bash
> langflow runTraceback (most recent call last): File ".../langflow", line 5, in <module>  from langflow.__main__ import mainModuleNotFoundError: No module named 'langflow.__main__'
```

There are two possible reasons for this error:

1. You've installed Langflow using `pip install langflow` but you already had a previous version of Langflow installed in your system. In this case, you might be running the wrong executable. To solve this issue, run the correct executable by running `python -m langflow run` instead of `langflow run`. If that doesn't work, try uninstalling and reinstalling Langflow with `uv pip install langflow --pre -U`.
2. Some version conflicts might have occurred during the installation process. Run `python -m pip install langflow --pre -U --force-reinstall` to reinstall Langflow and its dependencies.

#### Something went wrong running migrations

```bash
> Something went wrong running migrations. Please, run 'langflow migration --fix'
```

Clear the cache by deleting the contents of the cache folder.

This folder can be found at:

- **Linux or WSL2 on Windows**: `home/<username>/.cache/langflow/`
- **MacOS**: `/Users/<username>/Library/Caches/langflow/`

This error can occur during Langflow upgrades when the new version can't override `langflow-pre.db` in `.cache/langflow/`. Clearing the cache removes this file but also erases your settings.

If you wish to retain your files, back them up before clearing the folder.

#### Langflow installation freezes at pip dependency resolution

Installing Langflow with `pip install langflow` slowly fails with this error message:

```text
pip is looking at multiple versions of <<library>> to determine which version is compatible with other requirements. This could take a while.
```

To work around this issue, install Langflow with [`uv`](https://docs.astral.sh/uv/getting-started/installation/) instead of `pip`.

```text
uv pip install langflow
```

To run Langflow with uv:

```text
uv run langflow run
```

#### Failed to build required package

When you try to install Langflow on Linux, installation fails because of outdated or missing packages.

```bash
Resolved 455 packages in 18.92s
  × Failed to build `webrtcvad==2.0.10`
  ├─▶ The build backend returned an error
  ╰─▶ Call to `setuptools.build_meta:__legacy__.build_wheel` failed (exit status: 1)
```

1. Install the required build dependencies.

```bash
sudo apt-get update
sudo apt-get install build-essential python3-dev
```

2. If upgrading your packages doesn't fix the issue, install `gcc` separately.

```bash
sudo apt-get install gcc
```

## Install and run Langflow Desktop

:::important
Langflow Desktop is in **Alpha**.
Development is ongoing, and the features and functionality are subject to change.
:::

**Langflow Desktop** is a desktop version of Langflow that includes all the features of open source Langflow, with an additional [version management](#manage-your-langflow-version-in-langflow-desktop) feature for managing your Langflow version.

:::important
Langflow Desktop is available only for macOS.
:::

To install Langflow Desktop, follow these steps:

1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
2. Enter your **Name**, **Email address**, and **Company**, and then click **Download**.
3. Open the **Finder**, and then navigate to **Downloads**.
4. Double-click the downloaded `*.dmg` file.
5. To install Langflow Desktop, drag and drop the application icon to the **Applications** folder.
6. When the installation completes, open the Langflow application.

The application checks [uv](https://docs.astral.sh/uv/concepts/tools/), your local environment, and the Langflow version, and then starts.

### Manage your Langflow version in Langflow Desktop

When a new version of Langflow is available, Langflow Desktop displays an upgrade message.

To manage your Langflow version in Langflow Desktop, follow these steps:

1. To access Langflow Desktop's **Version Management** pane, click your **Profile Image**, and then select **Version Management**.
Langflow Desktop's current version is displayed, with other version options listed after it.
The **latest** version is always highlighted.
2. To change your Langflow version, select another version.
A confirmation pane containing the selected version's changelog appears.
3. To change to the selected version, click **Confirm**.
The application restarts with the new version installed.

## DataStax Langflow {#datastax-langflow}

**DataStax Langflow** is a hosted version of Langflow integrated with [Astra DB](https://www.datastax.com/products/datastax-astra). Be up and running in minutes with no installation or setup required. [Sign up for free](https://astra.datastax.com/signup?type=langflow).
