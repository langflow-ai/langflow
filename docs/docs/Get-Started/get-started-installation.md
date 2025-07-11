---
title: Install Langflow
slug: /get-started-installation
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow can be installed in multiple ways:

* [**Langflow Desktop (Recommended)**](#install-and-run-langflow-desktop): Download and install the standalone desktop application for the least complicated setup experience.
This option includes dependency management and facilitated upgrades.

* [**Docker**](#install-and-run-langflow-docker): Pull and run the Langflow Docker image to start a Langflow container and run Langflow in isolation.

* [**Python package**](#install-and-run-the-langflow-oss-python-package): Install and run the Langflow OSS Python package.
This option offers more control over the environment, dependencies, and versioning.

* [**Install from source**](/contributing-how-to-contribute#install-langflow-from-source): Use this option if you want to contribute to the Langflow codebase or documentation.

## Install and run Langflow Desktop

Langflow Desktop is a desktop version of Langflow that simplifies dependency management and upgrades.
However, some features aren't available for Langflow Desktop, such as the **Shareable Playground**.

<Tabs groupId="os">
  <TabItem value="macOS" label="macOS">

  1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
  2. Click **Download Langflow**, enter your contact information, and then click **Download**.
  3. Mount and install the Langflow application.
  4. When the installation completes, open the Langflow application, and then create your first flow with the [Quickstart](/get-started-quickstart).

  </TabItem>
  <TabItem value="Windows" label="Windows">

  1. Navigate to [Langflow Desktop](https://www.langflow.org/desktop).
  2. Click **Download Langflow**, enter your contact information, and then click **Download**.
  3. Open the **File Explorer**, and then navigate to **Downloads**.
  4. Double-click the downloaded `.msi` file, and then use the install wizard to install Langflow Desktop.

      :::important
      Windows installations of Langflow Desktop require a C++ compiler that may not be present on your system. If you receive a `C++ Build Tools Required!` error, follow the on-screen prompt to install Microsoft C++ Build Tools, or [install Microsoft Visual Studio](https://visualstudio.microsoft.com/downloads/).
      :::

  5. When the installation completes, open the Langflow application, and then create your first flow with the [Quickstart](/get-started-quickstart).

  </TabItem>
</Tabs>

For upgrade information, see the [Release notes](/release-notes).

To manage dependencies in Langflow Desktop, see [Install custom dependencies in Langflow Desktop](/install-custom-dependencies#langflow-desktop).

## Install and run Langflow with Docker {#install-and-run-langflow-docker}

You can use the Langflow Docker image to start a Langflow container.
For more information, see [Deploy Langflow on Docker](/deployment-docker).

1. Install and start [Docker](https://docs.docker.com/).

2. Pull the latest [Langflow Docker image](https://hub.docker.com/r/langflowai/langflow) and start it:

    ```bash
    docker run -p 7860:7860 langflowai/langflow:latest
    ```

3. To access Langflow, navigate to `http://localhost:7860/`.

4. Create your first flow with the [Quickstart](/get-started-quickstart).

## Install and run the Langflow OSS Python package

1. Make sure you have the required dependencies and infrastructure:

    - [Python](https://www.python.org/downloads/release/python-3100/)
       - macOS and Linux: Version 3.10 to 3.13
       - Windows: Version 3.10 to 3.12
    - [uv](https://docs.astral.sh/uv/getting-started/installation/)
    - Sufficient infrastructure:
       - Minimum: Dual-core CPU and 2 GB RAM
       - Recommended: Multi-core CPU and at least 4 GB RAM

2. Create a virtual environment with [uv](https://docs.astral.sh/uv/pip/environments).

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

3. In your virtual environment, install Langflow:

    ```bash
    uv pip install langflow
    ```

    To install a specific version of the Langflow package by adding the required version to the command, such as `uv pip install langflow==1.4.22`.

    <details>
    <summary>Reinstall or upgrade Langflow</summary>

    To reinstall Langflow and all of its dependencies, run `uv pip install langflow --force-reinstall`.

    To upgrade Langflow to the latest version, run `uv pip install langflow -U`.
    However, the Langflow team recommends taking steps to backup your existing installation before you upgrade Langflow.
    For more information, see [Prepare to upgrade](/release-notes#prepare-to-upgrade).

    </details>

4. Start Langflow:

    ```bash
    uv run langflow run
    ```

    It can take a few minutes for Langflow to start.

5. To confirm that a local Langflow instance is running, navigate to the default Langflow URL `http://127.0.0.1:7860`.

6. Create your first flow with the [Quickstart](/get-started-quickstart).

For upgrade information, see the [Release notes](/release-notes).

For information about optional dependency groups and support for custom dependencies to extend Langflow OSS functionality, see [Install custom dependencies](/install-custom-dependencies).

## Next steps

* [Quickstart](/get-started-quickstart): Build and run your first flow in minutes.
* [Build flows](/concepts-flows): Learn about building flows.
* [Troubleshoot Langflow](/troubleshoot): Get help with common Langflow install and startup issues.