---
title: Langflow release notes
slug: /release-notes
---

This page summarizes significant changes and updates to Langflow.

For the complete changelog, see the [Changelog](https://github.com/langflow-ai/langflow/releases/latest).

## 1.5.0

The following updates are included in this version:

### New features and enhancements

- Authentication changes

    All API endpoints now require a Langflow API key to function, even when [LANGFLOW_AUTO_LOGIN](/environment-variables#LANGFLOW_AUTO_LOGIN) is enabled. This change enhances security by ensuring that automatic login features are properly authenticated.
    The only exceptions are for the MCP endpoints at `/v1/mcp`, `/v1/mcp-projects`, and `/v2/mcp`, which will not require API keys.
    For more information, see [API keys](/configuration-api-keys).

- New Language Model and Embedding Model components

    The **Language Model** and **Embedding Model** components have been promoted to be the main components for your LLM and embeddings flows. They support multiple models and model providers, and allow you to experiment without swapping out single-provider components.
    The single-provider components are still available for your flows in the components sidebar under [Bundles](/components-bundles).
    For more information, see the [Language model](/components-models) and [Embedding model](/components-embedding-models) components.

- MCP one-click installation

    In the **MCP server** page, click **Auto install** to install your Langflow MCP server to MCP clients with just one click.
    The option to install with a JSON configuration file is available for macOS, Windows, and WSL.
    For more information, see [MCP server](/mcp-server).

- Input schema replaces temporary overrides

    The **Input schema** pane replaces the need to manage tweak values in the **API access** pane. When you enable a parameter in the **Input schema** pane, the parameter is automatically added to your flow’s code snippets, providing ready-to-use templates for making requests in your preferred programming language.

- Tools category is now legacy

    All components in the **Tools** category are now **Legacy** or have moved to [Bundles](/components-bundles).

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