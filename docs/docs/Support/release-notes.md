---
title: Langflow release notes
slug: /release notes
---

This page summarizes significant changes and updates to Langflow.


## 1.5

* Moved **Model** and **Embedding Model** components to the [](/components-bundles) in the sidebar, and replaced them with preferred **Language Model** and **Embedding Model** components. These components are satisfactory for most use cases, and the single-provider components are still available for your flows.
For more information, examples, and parameters, see [Model components](/components-models).

* MCP one-click installation: In the **MCP server** page, click **Auto install** to install your Langflow MCP server to Claude or Cursor clients with just one click.

* Input schema replaces temporary overrides: Instead of managing the tweaks values in the **API access** pane, this pane now adds them to the code snippets for this flow. This still provides a template for sending the request in your language of choice, and presents a default value for you to modify to suit your application's needs.


### 1.4.2

The following updates are included in this version:

### New features and enhancements
- Enhanced file and flow management system with improved bulk capabilities.

### New integrations and bundles
- BigQuery component for connecting to BQ datasets.
- Twelve Labs integration bundle.
- NVIDIA system assistant component.

### Deprecated features

- Deprecated the Combine text component.

### 1.4.1

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