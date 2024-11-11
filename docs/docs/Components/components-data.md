---
title: Data
sidebar_position: 3
slug: /components-data
---

## API Request

This component sends HTTP requests to the specified URLs.

Use this component to interact with external APIs or services and retrieve data. Ensure that the URLs are valid and that you configure the method, headers, body, and timeout correctly.

### Parameters

#### Inputs

| Name    | Display Name | Info                                                                       |
| ------- | ------------ | -------------------------------------------------------------------------- |
| URLs    | URLs         | The URLs to target                                                         |
| curl    | curl         | Paste a curl command to fill in the dictionary fields for headers and body |
| Method  | HTTP Method  | The HTTP method to use, such as GET or POST                                |
| Headers | Headers      | The headers to include with the request                                    |
| Body    | Request Body | The data to send with the request (for methods like POST, PATCH, PUT)      |
| Timeout | Timeout      | The maximum time to wait for a response                                    |

## Directory

This component recursively loads files from a directory, with options for file types, depth, and concurrency.

### Parameters

| Input              | Type             | Description                                        |
| ------------------ | ---------------- | -------------------------------------------------- |
| path               | MessageTextInput | Path to the directory to load files from           |
| types              | MessageTextInput | File types to load (leave empty to load all types) |
| depth              | IntInput         | Depth to search for files                          |
| max_concurrency    | IntInput         | Maximum concurrency for loading files              |
| load_hidden        | BoolInput        | If true, hidden files will be loaded               |
| recursive          | BoolInput        | If true, the search will be recursive              |
| silent_errors      | BoolInput        | If true, errors will not raise an exception        |
| use_multithreading | BoolInput        | If true, multithreading will be used               |

| Output | Type       | Description                         |
| ------ | ---------- | ----------------------------------- |
| data   | List[Data] | Loaded file data from the directory |

## File

The FileComponent is a class that loads and parses text files of various supported formats, converting the content into a Data object. It supports multiple file types and provides an option for silent error handling.

### Parameters

#### Inputs

| Name          | Display Name  | Info                                         |
| ------------- | ------------- | -------------------------------------------- |
| path          | Path          | File path to load.                           |
| silent_errors | Silent Errors | If true, errors will not raise an exception. |

#### Outputs

| Name | Display Name | Info                                         |
| ---- | ------------ | -------------------------------------------- |
| data | Data         | Parsed content of the file as a Data object. |

## URL

The URLComponent is a class that fetches content from one or more URLs, processes the content, and returns it as a list of Data objects. It ensures that the provided URLs are valid and uses WebBaseLoader to fetch the content.

### Parameters

#### Inputs

| Name | Display Name | Info                   |
| ---- | ------------ | ---------------------- |
| urls | URLs         | Enter one or more URLs |

#### Outputs

| Name | Display Name | Info                                                         |
| ---- | ------------ | ------------------------------------------------------------ |
| data | Data         | List of Data objects containing fetched content and metadata |

## Gmail Loader

This component loads emails from Gmail using provided credentials and filters.

For more on creating a service account JSON, see [Service Account JSON](https://developers.google.com/identity/protocols/oauth2/service-account).

### Parameters

| Input       | Type             | Description                                                                          |
| ----------- | ---------------- | ------------------------------------------------------------------------------------ |
| json_string | SecretStrInput   | JSON string containing OAuth 2.0 access token information for service account access |
| label_ids   | MessageTextInput | Comma-separated list of label IDs to filter emails                                   |
| max_results | MessageTextInput | Maximum number of emails to load                                                     |

| Output | Type | Description       |
| ------ | ---- | ----------------- |
| data   | Data | Loaded email data |

## Google Drive Loader

This component loads documents from Google Drive using provided credentials and a single document ID.

For more on creating a service account JSON, see [Service Account JSON](https://developers.google.com/identity/protocols/oauth2/service-account).

### Parameters

| Input       | Type             | Description                                                                          |
| ----------- | ---------------- | ------------------------------------------------------------------------------------ |
| json_string | SecretStrInput   | JSON string containing OAuth 2.0 access token information for service account access |
| document_id | MessageTextInput | Single Google Drive document ID                                                      |

| Output | Type | Description          |
| ------ | ---- | -------------------- |
| docs   | Data | Loaded document data |

## Google Drive Search

This component searches Google Drive files using provided credentials and query parameters.

For more on creating a service account JSON, see [Service Account JSON](https://developers.google.com/identity/protocols/oauth2/service-account).

### Parameters

| Input          | Type             | Description                                                                          |
| -------------- | ---------------- | ------------------------------------------------------------------------------------ |
| token_string   | SecretStrInput   | JSON string containing OAuth 2.0 access token information for service account access |
| query_item     | DropdownInput    | The field to query                                                                   |
| valid_operator | DropdownInput    | Operator to use in the query                                                         |
| search_term    | MessageTextInput | The value to search for in the specified query item                                  |
| query_string   | MessageTextInput | The query string used for searching (can be edited manually)                         |

| Output     | Type      | Description                                     |
| ---------- | --------- | ----------------------------------------------- |
| doc_urls   | List[str] | URLs of the found documents                     |
| doc_ids    | List[str] | IDs of the found documents                      |
| doc_titles | List[str] | Titles of the found documents                   |
| Data       | Data      | Document titles and URLs in a structured format |

## Webhook

This component defines a webhook input for the flow. The flow can be triggered by an external HTTP POST request (webhook) sending a JSON payload.

If the input is not valid JSON, the component will wrap it in a "payload" field. The component's status will reflect any errors or the processed data.

### Parameters

#### Inputs

| Name | Type   | Description                                    |
| ---- | ------ | ---------------------------------------------- |
| data | String | JSON payload for testing the webhook component |

#### Outputs

| Name        | Type | Description                           |
| ----------- | ---- | ------------------------------------- |
| output_data | Data | Processed data from the webhook input |
