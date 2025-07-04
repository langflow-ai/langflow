---
title: Install Langflow
slug: /get-started-installation
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow can be installed in multiple ways:

* **Langflow Desktop (Recommended)**: Download and install the [standalone desktop application](#install-and-run-langflow-desktop) for the easiest setup experience.

* **Docker**: Pull and run the [Docker image](#install-and-run-langflow-docker) to start a Langflow container.

* **Python package**: Install the [Langflow OSS Python package](#install-and-run-the-langflow-oss-python-package).

## Install and run Langflow Desktop

**Langflow Desktop** is a desktop version of Langflow that includes all the features of open source Langflow, with an additional [version management](#manage-your-version-of-langflow-desktop) feature for managing your Langflow version.

<Tabs groupId="os">
  <TabItem value="macOS" label="macOS">

  1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
  2. Click **Download Langflow**, enter your contact information, and then click **Download**.
  3. Mount and install the Langflow application.
  4. When the installation completes, open the Langflow application.

  After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

  </TabItem>
  <TabItem value="Windows" label="Windows">

  1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
  2. Click **Download Langflow**, enter your contact information, and then click **Download**.
  3. Open the **File Explorer**, and then navigate to **Downloads**.
  4. Double-click the downloaded `.msi` file, and then use the install wizard to install Langflow Desktop.

      :::important
      Windows installations of Langflow Desktop require a C++ compiler that may not be present on your system. If you receive a `C++ Build Tools Required!` error, follow the on-screen prompt to install Microsoft C++ Build Tools, or [install Microsoft Visual Studio](https://visualstudio.microsoft.com/downloads/).
      :::

  5. When the installation completes, open the Langflow application.

  After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

  </TabItem>
</Tabs>

  After confirming that Langflow is running, create your first flow with the [Quickstart](/get-started-quickstart).

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

### Install Langflow from source

To install Langflow from source, see [Install Langflow from source](/contributing-how-to-contribute#install-langflow-from-source).

### Manage Langflow OSS versions

:::important
The Langflow team recommends installing new Langflow versions in a new virtual environment before upgrading your primary installation.

This allows you to [import flows](/concepts-flows#import-flow) from your existing installation and test them in the new version without disrupting your existing installation.
In the event of breaking changes or bugs, your existing installation is preserved in a stable state.
:::

To manage your Langflow OSS version, use the following commands:

* Upgrade Langflow to the latest version: `uv pip install langflow -U`
* Install a specific version of the Langflow package by adding the required version to the command, such as: `uv pip install langflow==1.3.2`
* Reinstall Langflow and all of its dependencies: `uv pip install langflow --force-reinstall`

### Manage Langflow OSS dependencies

Langflow OSS provides optional dependency groups and support for custom dependencies to extend Langflow functionality.
For more information, see [Install custom dependencies](/install-custom-dependencies).

## Troubleshoot Langflow installation and startup issues

If you encounter an issue when installing or running Langflow, see [Troubleshoot Langflow](/troubleshoot).

## Next steps

After installing Langflow, build and run a flow with the [quickstart](/get-started-quickstart).