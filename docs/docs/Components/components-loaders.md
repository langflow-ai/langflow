---
title: Loaders
sidebar_position: 10
slug: /components-loaders
---

# Loaders

Loaders are components used to load documents from various sources, such as databases, websites, and local files. They can be used to fetch data from external sources and convert it into a format that can be processed by other components.

## Confluence

The Confluence component integrates with the Confluence wiki collaboration platform to load and process documents. It utilizes the ConfluenceLoader from LangChain to fetch content from a specified Confluence space.

### Parameters

#### Inputs:

| Name | Display Name | Info |
| --- | --- | --- |
| url | Site URL | The base URL of the Confluence Space (e.g., https://company.atlassian.net/wiki) |
| username | Username | Atlassian User E-mail (e.g., email@example.com) |
| api_key | API Key | Atlassian API Key (Create at: https://id.atlassian.com/manage-profile/security/api-tokens) |
| space_key | Space Key | The key of the Confluence space to access |
| cloud | Use Cloud? | Whether to use Confluence Cloud (default: true) |
| content_format | Content Format | Specify content format (default: STORAGE) |
| max_pages | Max Pages | Maximum number of pages to retrieve (default: 1000) |

#### Outputs:

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | List of Data objects containing the loaded Confluence documents |

## GitLoader

The GitLoader component uses the GitLoader from LangChain to fetch and load documents from a specified Git repository.

### Parameters

#### Inputs:

| Name | Display Name | Info |
| --- | --- | --- |
| repo_path | Repository Path | The local path to the Git repository |
| clone_url | Clone URL | The URL to clone the Git repository from (optional) |
| branch | Branch | The branch to load files from (default: 'main') |
| file_filter | File Filter | Patterns to filter files (e.g., '.py' to include only .py files, '!.py' to exclude .py files) |
| content_filter | Content Filter | A regex pattern to filter files based on their content |

#### Outputs:

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | List of Data objects containing the loaded Git repository documents |

## Unstructured

This component uses the [Unstructured.io](https://unstructured.io/) Serverless API to load and parse files into structured data.

### Parameters

#### Inputs:

| Name | Display Name | Info |
| --- | --- | --- |
| file | File | The path to the file to be parsed (supported types are listed [here](https://docs.unstructured.io/api-reference/api-services/overview#supported-file-types)) |
| api_key | API Key | Unstructured.io Serverless API Key |

#### Outputs:

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | List of Data objects containing the parsed content from the input file |
