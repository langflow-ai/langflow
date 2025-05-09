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

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
| --- | --- | --- |
| url | Site URL | The base URL of the Confluence Space, for example https://company.atlassian.net/wiki. |
| username | Username | The Atlassian User E-mail, for example email@example.com. |
| api_key | API Key | The Atlassian API Key. Create an API key at [Atlassian](https://id.atlassian.com/manage-profile/security/api-tokens). |
| space_key | Space Key | The key of the Confluence space to access. |
| cloud | Use Cloud? | Whether to use Confluence Cloud. Default is true. |
| content_format | Content Format | The content format. Default is STORAGE. |
| max_pages | Max Pages | The maximum number of pages to retrieve. Default is 1000. |

**Outputs**

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | A list of Data objects containing the loaded Confluence documents. |

</details>

## GitLoader

The GitLoader component uses the GitLoader from LangChain to fetch and load documents from a specified Git repository.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
| --- | --- | --- |
| repo_path | Repository Path | The local path to the Git repository. |
| clone_url | Clone URL | The URL to clone the Git repository from. This field is optional. |
| branch | Branch | The branch to load files from. Default is main. |
| file_filter | File Filter | The patterns to filter files. Use .py to include only Python files, or !.py to exclude Python files. |
| content_filter | Content Filter | A regex pattern to filter files based on their content. |

**Outputs**

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | A list of Data objects containing the loaded Git repository documents. |

</details>

## Unstructured

This component uses the [Unstructured.io](https://unstructured.io/) Serverless API to load and parse files into a list of structured [Data](/concepts-objects) objects.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
| --- | --- | --- |
| file | File | The path to the file to be parsed. Supported types are listed in the [Unstructured documentation](https://docs.unstructured.io/api-reference/api-services/overview#supported-file-types). |
| api_key | API Key | The Unstructured.io Serverless API Key. |
| api_url | Unstructured.io API URL | The URL for the Unstructured API. This field is optional. |
| chunking_strategy | Chunking Strategy | The strategy for chunking the document. Options include basic, by_title, by_page, and by_similarity. |
| unstructured_args | Additional Arguments | A dictionary of additional arguments for the Unstructured.io API. This field is optional. |

**Outputs**

| Name | Display Name | Info |
| --- | --- | --- |
| data | Data | A list of Data objects containing the parsed content from the input file. |

</details>
