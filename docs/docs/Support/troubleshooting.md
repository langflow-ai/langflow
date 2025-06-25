---
title: Troubleshoot Langflow
slug: /troubleshoot
---

This page provides troubleshooting advice for issues you might encounter when using Langflow or contributing to Langflow.

## Missing components

As Langflow development continues, components are often recategorized or deprecated for better alignment or to prepare for new components.

If a component appears to be missing from the expected location on the **Components** menu, try the following:

* Search for the component or check other component categories, including [Bundles](/components-bundle-components).
* [Expose legacy components](/concepts-components#component-menus), which are hidden by default.
* Check the [Changelog](https://github.com/langflow-ai/langflow/releases/latest) for component changes in recent releases.
* Make sure the component isn't already present in your flow if it is a single-use component.

If you still cannot locate the component, see [Langflow GitHub Issues and Discussions](/contributing-github-issues).

## No input in the Playground

If there is no text box for input in the Playground, make sure your flow has a [Input component](/components-io) that is connected to the **Input** port of another component.

## Missing key, no key found, or invalid API key

If you get an API key error when running a flow, try the following:

* For all components that require credentials, make sure those components have a valid credential in the component's settings, such as the **API key** field.
* If you store your credentials in [Langflow global variables](/configuration-global-variables), make sure you selected the correct global variable and that the variable contains a valid credential.
* Make sure the provided credentials are active, have the required permissions, and, if applicable, have sufficient funds in the account to execute the required action. For example, model providers require credits to use their LLMs.

## Langflow installation issues

The following issues can occur when installing Langflow.

### Langflow installation freezes at pip dependency resolution

Installing Langflow OSS with `pip install langflow` slowly fails with this error message:

```text
pip is looking at multiple versions of <<library>> to determine which version is compatible with other requirements. This could take a while.
```

To work around this issue, install Langflow with `uv` instead of `pip`, as explained in [Install and run the Langflow OSS Python package](/get-started-installation#install-and-run-the-langflow-oss-python-package).

### Linux installation fails to build required package

When you try to install Langflow OSS on Linux, installation fails because of outdated or missing packages:

```bash
Resolved 455 packages in 18.92s
  × Failed to build `webrtcvad==2.0.10`
  ├─▶ The build backend returned an error
  ╰─▶ Call to `setuptools.build_meta:__legacy__.build_wheel` failed (exit status: 1)
```

To resolve this error, install the required build dependencies, and then retry the Langflow installation:

```bash
sudo apt-get update
sudo apt-get install build-essential python3-dev
```

If upgrading your packages doesn't fix the issue, install `gcc` separately, and then retry the Langflow installation:

```bash
sudo apt-get install gcc
```

### Installation failure from `webrtcvad` package

If you experience an error from the `webrtcvad` package, run `uv pip install webrtcvad-wheels` in your virtual environment, and then retry the Langflow installation.

## Langflow startup issues

The following issues can occur when attempting to start Langflow.

### No `langflow.__main__` module

When you try to run Langflow with the command `langflow run`, you encounter the following error:

```bash
> No module named 'langflow.__main__'
```

To resolve this issue, try the following:

1. Run `uv run langflow run` instead of `langflow run`.
2. If that doesn't work, reinstall the latest Langflow version with `uv pip install langflow -U`.
3. If that doesn't work, reinstall Langflow and its dependencies with `uv pip install langflow --pre -U --force-reinstall`.

### Langflow runTraceback

When you try to run Langflow using the command `langflow run`, you encounter the following error:

```bash
> langflow runTraceback (most recent call last): File ".../langflow", line 5, in <module>  from langflow.__main__ import mainModuleNotFoundError: No module named 'langflow.__main__'
```

There are two possible reasons for this error:

* **Multiple Langflow installations**: You installed Langflow using `pip install langflow` but you already had a previous version of Langflow installed in your system. In this case, you might be running the wrong executable.

    To solve this issue, run the correct executable by running `python -m langflow run` instead of `langflow run`.

    If that doesn't work, try uninstalling and reinstalling Langflow with `uv pip install langflow --pre -U`.

* **Version conflict during installation**: Some version conflicts might have occurred during the installation process. To resolve this issue, reinstall Langflow and its dependencies by running `python -m pip install langflow --pre -U --force-reinstall`.

## Langflow upgrade issues

The following issues can occur when upgrading your Langflow version.

For information about managing Langflow versions, see [Install Langflow](/get-started-installation).

### Something went wrong running migrations

The following error can occur during Langflow upgrades when the new version can't override `langflow-pre.db` in the Langflow cache folder:

```bash
> Something went wrong running migrations. Please, run 'langflow migration --fix'
```

To resolve this error, clear the cache by deleting the contents of the Langflow cache folder.

:::important
Clearing the cache erases your settings.
If you want to retain your settings files, create a backup of those files before clearing the cache folder.
:::

The cache folder location depends on your OS:

- **Linux**: `home/<username>/.cache/langflow/`
- **WSL2 on Windows**: `home/<username>/.cache/langflow/`
- **macOS**: `/Users/<username>/Library/Caches/langflow/`

## MCP server issues

- [Use MCP Inspector to test and debug flows](/mcp-server#test-and-debug-flows)
- [Troubleshooting MCP server](/mcp-server#troubleshooting-mcp-server)

## Custom components and integrations issues

For troubleshooting advice for a third-party integration, see the information about that integration in the Langflow documentation and the provider's documentation.

If you are building a custom component, see [Error handling and logging for custom Python components](/components-custom-components#error-handling-and-logging).

## See also

- [Langflow GitHub Issues and Discussions](/contributing-github-issues)
- [Langflow telemetry](/contributing-telemetry)