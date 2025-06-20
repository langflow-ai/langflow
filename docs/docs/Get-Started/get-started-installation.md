---
title: Install Langflow
slug: /get-started-installation
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow can be installed in multiple ways:

* **Langflow Desktop (Recommended)**: Download and install the [standalone desktop application](#install-and-run-langflow-desktop) for the easiest setup experience.

* **Docker**: Pull and run the [Docker image](#install-and-run-langflow-docker) to start a Langflow container.

* **Python package**: Install the [Langflow OSS Python package](#install-and-run-langflow-oss).

## Install and run Langflow Desktop

**Langflow Desktop** is a desktop version of Langflow that includes all the features of open source Langflow, with an additional [version management](#manage-your-langflow-version-in-langflow-desktop) feature for managing your Langflow version.

<Tabs groupId="os">
  <TabItem value="macOS" label="macOS">

  1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
  2. Click **Download Langflow**, enter your contact information, and then click **Download**.
  3. Mount and install the Langflow application.
  4. When the installation completes, open the Langflow application.

  After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

  </TabItem>
  <TabItem value="Windows" label="Windows">
    :::important
    Windows installations of Langflow Desktop require a C++ compiler, such as [Visual Studio](https://visualstudio.microsoft.com/downloads/), that may not be present on your system. If you receive a `C++ Build Tools Required!` error, follow the on-screen prompt to install Microsoft C++ Build Tools, or visit the Visual Studio download link above.
    :::

  1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
  2. Click **Download Langflow**, enter your contact information, and then click **Download**.
  3. Open the **File Explorer**, and then navigate to **Downloads**.
  4. Double-click the downloaded `.msi` file, and then use the install wizard to install Langflow Desktop.
  6. When the installation completes, open the Langflow application.

  After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

  </TabItem>

</Tabs>

### Manage your version of Langflow Desktop

When a new version of Langflow is available, Langflow Desktop displays an upgrade message.

To manage your version of Langflow Desktop, follow these steps:

  1. In Langflow Desktop, click your profile image, and then select **Version Management**.
  The **Version Management** pane lists your active Langflow version first, followed by other available versions.
  The **latest** version is always highlighted.
  2. To change your Langflow version, select another version.
  A confirmation pane containing the selected version's changelog appears.
  3. To apply the change, click **Confirm**.
  Langflow desktop restarts to install and activate the new version.

## Install and run Langflow with Docker {#install-and-run-langflow-docker}

You can use the [Langflow Docker image](https://hub.docker.com/r/langflowai/langflow) to run Langflow in an isolated environment.
Running applications in [Docker](https://docs.docker.com/) containers ensures consistent behavior across different systems and eliminates dependency conflicts.

1. Install and start [Docker](https://docs.docker.com/).
2. Pull the latest [Langflow Docker image](https://hub.docker.com/r/langflowai/langflow) and start it:

  ```bash
  docker run -p 7860:7860 langflowai/langflow:latest
  ```

3. To access Langflow, navigate to `http://localhost:7860/`.

For more information, see [Deploy Langflow on Docker](/deployment-docker).

## Install and run the Langflow OSS Python package

To install and run Langflow OSS, you need the following:

- [Python 3.10 to 3.13](https://www.python.org/downloads/release/python-3100/) for macOS/Linux, and Python 3.10 to 3.12 for Windows
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- At minimum, a dual-core CPU and 2 GB RAM, but a multi-core CPU and at least 4 GB RAM are recommended

1. Create a virtual environment with [uv](https://docs.astral.sh/uv/pip/environments).

<details>
<summary>Need help with virtual environments?</summary>

Virtual environments ensure Langflow is installed in an isolated, fresh environment.
To create a new virtual environment, do the following.

<Tabs groupId="os">
  <TabItem value="macOS/Linux" label="macOS/Linux" default>
    1. Navigate to where you want your virtual environment to be created, and create it with `uv`.
Replace `VENV_NAME` with your preferred name for your virtual environment.
```
uv venv VENV_NAME
```
2. Start the virtual environment.
```
source VENV_NAME/bin/activate
```
Your shell's prompt changes to display that you're currently working in a virtual environment.
```
(VENV_NAME) ➜  langflow git:(main) ✗
```
3. To deactivate the virtual environment and return to your regular shell, type `deactivate`.
   When activated, the virtual environment temporarily modifies your PATH variable to prioritize packages installed within the virtual environment, so always deactivate it when you're done to avoid conflicts with other projects.
To delete the virtual environment, type `rm -rf VENV_NAME`.
  </TabItem>
  <TabItem value="Windows" label="Windows">
1. Navigate to where you want your virtual environment to be created, and create it with `uv`.
Replace `VENV_NAME` with your preferred name for your virtual environment.
```
uv venv VENV_NAME
```
2. Start the virtual environment.
```shell
VENV_NAME\Scripts\activate
```
Your shell's prompt changes to display that you're currently working in a virtual environment.
```
(VENV_NAME) PS C:/users/username/langflow-dir>
```
3. To deactivate the virtual environment and return to your regular shell, type `deactivate`.
   When activated, the virtual environment temporarily modifies your PATH variable to prioritize packages installed within the virtual environment, so always deactivate it when you're done to avoid conflicts with other projects.
To delete the virtual environment, type `Remove-Item VENV_NAME`.
  </TabItem>
  </Tabs>

</details>

2. To install Langflow, run the following command.
  ```bash
  uv pip install langflow
  ```

3. After installation, start Langflow:
  ```bash
  uv run langflow run
  ```

4. To confirm that a local Langflow instance is running, navigate to the default Langflow URL `http://127.0.0.1:7860`.
It can take a few minutes for Langflow to start.

After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

### Manage Langflow OSS versions

To manage your Langflow version, use the following commands.

<details closed>
<summary>Manage Langflow OSS versions</summary>

To upgrade Langflow to the latest version:

```bash
uv pip install langflow -U
```

To install a specific version of the Langflow package, add the required version to the command:

```bash
uv pip install langflow==1.3.2
```

To reinstall Langflow and all of its dependencies, add the `--force-reinstall` flag to the command:

```bash
uv pip install langflow --force-reinstall
```

</details>


### Manage Langflow OSS dependencies

Langflow OSS provides optional dependency groups that extend its functionality.

These dependencies are listed in the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L191) file under `[project.optional-dependencies]`.

<details closed>
<summary>Install dependency groups</summary>

Install dependency groups using pip's `[extras]` syntax. For example, to install Langflow with the `postgresql` dependency group, enter the following command:

```bash
uv pip install "langflow[postgresql]"
```

To install multiple extras, enter the following command:

```bash
uv pip install "langflow[deploy,local,postgresql]"
```

To add your own custom dependencies, see [Install custom dependencies](/install-custom-dependencies).

</details>

### Common OSS installation issues

This is a list of possible issues that you may encounter when installing and running Langflow.

<details>
<summary>No <code>langflow.__main__</code> module</summary>

When you try to run Langflow with the command `langflow run`, you encounter the following error:

```bash
> No module named 'langflow.__main__'
```

1. Run `uv run langflow run` instead of `langflow run`.
2. If that doesn't work, reinstall the latest Langflow version with `uv pip install langflow -U`.
3. If that doesn't work, reinstall Langflow and its dependencies with `uv pip install langflow --pre -U --force-reinstall`.

</details>

<details>
<summary>Langflow runTraceback</summary>

When you try to run Langflow using the command `langflow run`, you encounter the following error:

```bash
> langflow runTraceback (most recent call last): File ".../langflow", line 5, in <module>  from langflow.__main__ import mainModuleNotFoundError: No module named 'langflow.__main__'
```

There are two possible reasons for this error:

1. You've installed Langflow using `pip install langflow` but you already had a previous version of Langflow installed in your system. In this case, you might be running the wrong executable. To solve this issue, run the correct executable by running `python -m langflow run` instead of `langflow run`. If that doesn't work, try uninstalling and reinstalling Langflow with `uv pip install langflow --pre -U`.
2. Some version conflicts might have occurred during the installation process. Run `python -m pip install langflow --pre -U --force-reinstall` to reinstall Langflow and its dependencies.

</details>

<details>
<summary>Something went wrong running migrations</summary>

```bash
> Something went wrong running migrations. Please, run 'langflow migration --fix'
```

Clear the cache by deleting the contents of the cache folder.

This folder can be found at:

- **Linux or WSL2 on Windows**: `home/<username>/.cache/langflow/`
- **MacOS**: `/Users/<username>/Library/Caches/langflow/`

This error can occur during Langflow upgrades when the new version can't override `langflow-pre.db` in `.cache/langflow/`. Clearing the cache removes this file but also erases your settings.

If you wish to retain your files, back them up before clearing the folder.

</details>

<details>
<summary>Langflow installation freezes at pip dependency resolution</summary>

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

</details>

<details>
<summary>Failed to build required package</summary>

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

</details>

<details>
<summary>Installation failure from <code>webrtcvad</code> package</summary>

If you experience an error from the `webrtcvad` package, run `uv pip install webrtcvad-wheels` in the virtual environment, and then try installing again.

</details>