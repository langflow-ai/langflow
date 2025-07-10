---
title: Langflow release notes
slug: /release-notes
---

This page summarizes significant changes to Langflow in each release.

For all changes, see the [Changelog](https://github.com/langflow-ai/langflow/releases/latest).

## Prepare to upgrade

To avoid the impact of potential breaking changes and test new versions, the Langflow team recommends the following:

1. [Export your projects](/api-projects#export-a-project) to create backups of your flows:

    ```bash
    curl -X GET \
    "$LANGFLOW_SERVER_URL/api/v1/projects/download/$PROJECT_ID" \
      -H "accept: application/json" \
      -H "x-api-key: $LANGFLOW_API_KEY"
    ```
2. Install the new version: 

   * **Langflow OSS Python package**: Install the new version in a new virtual environment, and then [import your flows](/concepts-flows) to test them in the new version.
   * **Langflow Docker image**: Run the new image in a separate container, and then [import your flows](/concepts-flows) to the version of Langflow running in the new container.
   * **Langflow Desktop**: Upgrade Langflow Desktop, as explained in [Manage your version of Langflow Desktop](/get-started-installation#manage-your-version-of-langflow-desktop). If you want to isolate the new version, you must install Langflow Desktop on a separate physical or virtual machine, and then  [import your flows](/concepts-flows) to the new installation.

4. Test your flows in the new version, [upgrading components](/concepts-components#component-versions) as needed.

    When upgrading components, you can use the **Create backup flow before updating** option if you didn't previously export your flows.

5. If you installed the new version in isolation, upgrade your primary installation after testing the new version.

    If you made changes to your flows in the isolated installation, you might want to export and import those flows back to your upgraded primary installation so you don't have to repeat the component upgrade process.

## 1.5.0

The following updates are included in this version:

### New features and enhancements

- Authentication changes

    All API endpoints now require a Langflow API key to function, even when [LANGFLOW_AUTO_LOGIN](/environment-variables#LANGFLOW_AUTO_LOGIN) is enabled. This change enhances security by ensuring that automatic login features are properly authenticated.
    The only exceptions are for the MCP endpoints at `/v1/mcp`, `/v1/mcp-projects`, and `/v2/mcp`, which will not require API keys.
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

    The **Input schema** pane replaces the need to manage tweak values in the **API access** pane. When you enable a parameter in the **Input schema** pane, the parameter is automatically added to your flow’s code snippets, providing ready-to-use templates for making requests in your preferred programming language.

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