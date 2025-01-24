---
title: Loaders
slug: /components-loaders
---

# Loader components in Langflow

:::info
As of Langflow 1.1, loader components are now found in the **Components** menu under **Bundles**.
:::

Loaders fetch data into Langflow from various sources, such as databases, websites, and local files.

## Use a loader component in a flow

This flow creates a question-and-answer chatbot for documents that are loaded into the flow.
The [Unstructured.io](https://unstructured.io/) loader component loads files from your local machine, and then parses them into a list of structured [Data](/concepts-objects) objects.
This loaded data informs the **Open AI** component's responses to your questions.

![Sample Flow retrieving data with unstructured](/img/starter-flow-unstructured-qa.png)

## Confluence

The Confluence component integrates with the Confluence wiki collaboration platform to load and process documents. It utilizes the ConfluenceLoader from LangChain to fetch content from a specified Confluence space.

### Inputs

| Name | Display Name | Info |
| --- | --- | --- |
| url | Site URL | The base URL of the Confluence Space (e.g., `https://company.atlassian.net/wiki`) |
| username | Username | Atlassian User E-mail (e.g., `email@example.com`) |
| api_key | API Key | Atlassian API Key (Create an API key at: [Atlassian](https://id.atlassian.com/manage-profile/security/api-tokens)) |
| space_key | Space Key | The key of the Confluence space to access |
| cloud | Use Cloud? | Whether to use Confluence Cloud (default: true) |
| content_format | Content Format | Specify content format (default: STORAGE) |
| max_pages | Max Pages | Maximum number of pages to retrieve (default: 1000) |

### Outputs

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | List of Data objects containing the loaded Confluence documents |

## GitLoader

The GitLoader component uses the GitLoader from LangChain to fetch and load documents from a specified Git repository.

### Inputs

| Name | Display Name | Info |
| --- | --- | --- |
| repo_path | Repository Path | The local path to the Git repository |
| clone_url | Clone URL | The URL to clone the Git repository from (optional) |
| branch | Branch | The branch to load files from (default: 'main') |
| file_filter | File Filter | Patterns to filter files (e.g., '.py' to include only .py files, '!.py' to exclude .py files) |
| content_filter | Content Filter | A regex pattern to filter files based on their content |

### Outputs

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | List of Data objects containing the loaded Git repository documents |

## Unstructured

This component uses the [Unstructured.io](https://unstructured.io/) Serverless API to load and parse files into a list of structured [Data](/concepts-objects) objects.

### Inputs

| Name | Display Name | Info |
| --- | --- | --- |
| file | File | The path to the file to be parsed (supported types are listed [here](https://docs.unstructured.io/api-reference/api-services/overview#supported-file-types)) |
| api_key | API Key | Unstructured.io Serverless API Key |
| api_url | Unstructured.io API URL | Optional URL for the Unstructured API |
| chunking_strategy | Chunking Strategy | Strategy for chunking the document (options: "", "basic", "by_title", "by_page", "by_similarity") |
| unstructured_args | Additional Arguments | Optional dictionary of additional arguments for the Unstructured.io API |

### Outputs

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | List of Data objects containing the parsed content from the input file |
