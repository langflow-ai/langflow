---
title: Langflow release notes
slug: /release-notes
---

This page summarizes significant changes to Langflow in each release.

For all changes, see the [Changelog](https://github.com/langflow-ai/langflow/releases/latest).

## Prepare to upgrade

:::important
Whenever possible, the Langflow team recommends installing new Langflow versions in a new virtual environment or VM before upgrading your primary installation.
This allows you to [import flows](/concepts-flows-import#import-a-flow) from your existing installation and test them in the new version without disrupting your existing installation.
In the event of breaking changes or bugs, your existing installation is preserved in a stable state.
:::

To avoid the impact of potential breaking changes and test new versions, the Langflow team recommends the following upgrade process:

1. Recommended: [Export your projects](/api-projects#export-a-project) to create backups of your flows:

    ```bash
    curl -X GET \
    "$LANGFLOW_SERVER_URL/api/v1/projects/download/$PROJECT_ID" \
      -H "accept: application/json" \
      -H "x-api-key: $LANGFLOW_API_KEY"
    ```

   To export flows from the Langflow UI, see [Import and export flows](/concepts-flows-import).

2. Install the new version:

   * **Langflow OSS Python package**: Install the new version in a new virtual environment. For instructions, see [Install and run the Langflow OSS Python package](/get-started-installation#install-and-run-the-langflow-oss-python-package).
   * **Langflow Docker image**: Run the new image in a separate container.
   * **Langflow Desktop**: To upgrade in place, open Langflow Desktop, and then click **Upgrade Available** in the header. If you want to isolate the new version, you must install Langflow Desktop on a separate physical or virtual machine, and then [import your flows](/concepts-flows-import) to the new installation.

   :::tip
   If you experience data loss after an in-place upgrade of Langflow Desktop, see [Unexpected data loss after Langflow Desktop upgrade](/troubleshoot#data-loss).
   :::

3. [Import your flows](/concepts-flows-import) to test them in the new version, [upgrading components](/concepts-components#component-versions) as needed.

    When upgrading components, you can use the **Create backup flow before updating** option if you didn't previously export your flows.

4. If you installed the new version in isolation, upgrade your primary installation after testing the new version.

    If you made changes to your flows in the isolated installation, you might want to export and import those flows back to your upgraded primary installation so you don't have to repeat the component upgrade process.

## 1.5.0

The following updates are included in this version:

### New features and enhancements

- Authentication changes

    To enhance security and ensure proper authentication for automatic login features, most API endpoints now require authentication with a Langflow API key, regardless of the `AUTO_LOGIN` setting.
    The only exceptions are the MCP endpoints `/v1/mcp`, `/v1/mcp-projects`, and `/v2/mcp`, which never require authentication.
    For more information, see [API keys](/configuration-api-keys).

- New Language Model and Embedding Model components

    The **Language Model** and **Embedding Model** components have been promoted to be the main components for your LLM and embeddings flows. They support multiple models and model providers, and allow you to experiment without swapping out single-provider components.
    The single-provider components are still available for your flows in the components sidebar under [Bundles](/components-bundle-components).
    For more information, see the [Language model](/components-models) and [Embedding model](/components-embedding-models) components.

- MCP one-click installation

    In the **MCP server** page, click **Auto install** to install your Langflow MCP server to MCP clients with just one click.
    The option to install with a JSON configuration file is available for macOS, Windows, and WSL.
    For more information, see [MCP server](/mcp-server).

- MCP server management

    Add, remove, and edit your MCP servers in the **MCP Tools** and **Settings** page.
    For more information, see [MCP client](/mcp-client).

- Input schema replaces temporary overrides

    The **Input schema** pane replaces the need to manage tweak values in the **API access** pane. When you enable a parameter in the **Input schema** pane, the parameter is automatically added to your flow's code snippets, providing ready-to-use templates for making requests in your preferred programming language.

- Tools category is now legacy

    All components in the **Tools** category are now **Legacy** or have moved to [Bundles](/components-bundle-components).

    The [MCP Tools](/mcp-client) component is available in the components sidebar under **Agents**.

    Many of the **Tools** components performed the same functions, like web search and API requests, so we combined this functionality into single components:

    * To replace legacy search components, use the [Web search](/components-data#web-search) component.
    * To replace legacy news aggregation components, use the [News search](/components-data#news-search) component.

- Stability improvements

    General stability improvements and bug fixes for enhanced reliability.
    See an issue? [Raise it on GitHub](https://github.com/langflow-ai/langflow/issues).

### New integrations and bundles

- [Cleanlab integration](/integrations-cleanlab)

## 1.4.2

The following updates are included in this version:

### New features and enhancements
- Enhanced file and flow management system with improved bulk capabilities.

### New integrations and bundles
- BigQuery component for connecting to BQ datasets.
- Twelve Labs integration bundle.
- NVIDIA system assistant component.

### Deprecated features

- Deprecated the Combine text component.

## 1.4.1

The following updates are included in this version:

### New features and enhancements

- Added an enhanced "Breaking Changes" feature to help update components during version updates without breaking flows.

## 1.4.0

The following updates are included in this version:

### New features and enhancements

- Introduced MCP server functionality to serve Langflow tools to MCP-compatible clients.
- Renamed "Folders" to "Projects". The `/folders` endpoints now redirect to `/projects`.

### Deprecated features

- Deprecated the Google Gmail, Drive, and Search components.