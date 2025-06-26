---
title: Langflow release notes
slug: /release-notes
---

This page summarizes significant changes and updates to Langflow.

For the complete changelog, see the [Changelog](https://github.com/langflow-ai/langflow/releases/latest).

## 1.5

The following updates are included in this version:

### New features and enhancements

- Authentication changes

    The **AUTO_LOGIN** functionality now requires an API key to function. This change enhances security by ensuring that automatic login features are properly authenticated.
    For more information, see [API keys](/configuration-api-keys).

- New Language Model and Embedding Model components

    We moved **Model** and **Embedding Model** components to **Bundles** in the Langflow sidebar. The **Language Model** and **Embedding Model** components are satisfactory for most use cases, and the single-provider components are still available for your flows.
    For more information, see the [Language model](/components-models) and [Embedding model](/components-embedding-models) components.

- MCP one-click installation

    In the **MCP server** page, click **Auto install** to install your Langflow MCP server to Claude or Cursor clients with just one click.
    For more information, see [MCP server](/mcp-server).

- Input schema replaces temporary overrides

    Instead of managing the tweaks values in the **API access** pane, the **Input schema** pane adds the default values to the code snippets for this flow. This provides a template for sending the request in your language of choice, with a default value for you to modify to suit your application's needs.

- Tools category is now legacy

    All components in the **Tools** category are now **Legacy** or have moved.

    The [MCP Connection](/mcp-client) component is available in **Data components**.

    Many of the components performed the same functions, like web search and API requests, so we combined this functionality into single components:

    * To replace legacy search components like Bing Search and Google, use the [Web search](/components-data#web-search) component.
    * To replace legacy news aggregation components, use the [News search](/components-data#news-search) component.

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