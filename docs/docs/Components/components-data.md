---
title: Data
slug: /components-data
---

# Data components in Langflow

Data components load data from a source into your flow.

They may perform some processing or type checking, like converting raw HTML data into text, or ensuring your loaded file is of an acceptable type.

## Use a data component in a flow

The **URL** data component loads content from a list of URLs.

In the component's **URLs** field, enter a comma-separated list of URLs you want to load. Alternatively, connect a component that outputs the `Message` type, like the **Chat Input** component, to supply your URLs with a component.

To output a `Data` type, in the **Output Format** dropdown, select **Raw HTML**.
To output a `Message` type, in the **Output Format** dropdown, select **Text**. This option applies postprocessing with the `data_to_text` helper function.

In this example of a document ingestion pipeline, the URL component outputs raw HTML to a text splitter, which splits the raw content into chunks for a vector database to ingest.

![URL component in a data ingestion pipeline](/img/url-component.png)

## API Request

This component makes HTTP requests using URLs or cURL commands.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| urls | URLs | Enter one or more URLs, separated by commas. |
| curl | cURL | Paste a curl command to populate the dictionary fields for headers and body. |
| method | Method | The HTTP method to use. |
| use_curl | Use cURL | Enable cURL mode to populate fields from a cURL command. |
| query_params | Query Parameters | The query parameters to append to the URL. |
| body | Body | The body to send with the request as a dictionary (for `POST`, `PATCH`, `PUT`). |
| headers | Headers | The headers to send with the request as a dictionary. |
| timeout | Timeout | The timeout to use for the request. |
| follow_redirects | Follow Redirects | Whether to follow http redirects. |
| save_to_file | Save to File | Save the API response to a temporary file |
| include_httpx_metadata | Include HTTPx Metadata | Include properties such as `headers`, `status_code`, `response_headers`, and `redirection_history` in the output. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The result of the API requests. |


## Directory

This component recursively loads files from a directory, with options for file types, depth, and concurrency.

### Inputs

| Input              | Type             | Description                                        |
| ------------------ | ---------------- | -------------------------------------------------- |
| path               | MessageTextInput | Path to the directory to load files from           |
| types              | MessageTextInput | File types to load (leave empty to load all types) |
| depth              | IntInput         | Depth to search for files                          |
| max_concurrency    | IntInput         | Maximum concurrency for loading files              |
| load_hidden        | BoolInput        | If true, hidden files are loaded               |
| recursive          | BoolInput        | If true, the search is recursive              |
| silent_errors      | BoolInput        | If true, errors do not raise an exception        |
| use_multithreading | BoolInput        | If true, multithreading is used               |


### Outputs

| Output | Type       | Description                         |
| ------ | ---------- | ----------------------------------- |
| data   | List[Data] | Loaded file data from the directory |

## File

The FileComponent is a class that loads and parses text files of various supported formats, converting the content into a Data object. It supports multiple file types and provides an option for silent error handling.

The maximum supported file size is 100 MB.

### Inputs

| Name          | Display Name  | Info                                         |
| ------------- | ------------- | -------------------------------------------- |
| path          | Path          | File path to load.                           |
| silent_errors | Silent Errors | If true, errors do not raise an exception. |

### Outputs

| Name | Display Name | Info                                         |
| ---- | ------------ | -------------------------------------------- |
| data | Data         | Parsed content of the file as a Data object. |

## Gmail Loader

This component loads emails from Gmail using provided credentials and filters.

For more on creating a service account JSON, see [Service Account JSON](https://developers.google.com/identity/protocols/oauth2/service-account).

### Inputs

| Input       | Type             | Description                                                                          |
| ----------- | ---------------- | ------------------------------------------------------------------------------------ |
| json_string | SecretStrInput   | JSON string containing OAuth 2.0 access token information for service account access |
| label_ids   | MessageTextInput | Comma-separated list of label IDs to filter emails                                   |
| max_results | MessageTextInput | Maximum number of emails to load                                                     |

### Outputs

| Output | Type | Description       |
| ------ | ---- | ----------------- |
| data   | Data | Loaded email data |

## Google Drive Loader

This component loads documents from Google Drive using provided credentials and a single document ID.

For more on creating a service account JSON, see [Service Account JSON](https://developers.google.com/identity/protocols/oauth2/service-account).

### Inputs

| Input       | Type             | Description                                                                          |
| ----------- | ---------------- | ------------------------------------------------------------------------------------ |
| json_string | SecretStrInput   | JSON string containing OAuth 2.0 access token information for service account access |
| document_id | MessageTextInput | Single Google Drive document ID                                                      |

### Outputs

| Output | Type | Description          |
| ------ | ---- | -------------------- |
| docs   | Data | Loaded document data |

## Google Drive Search

This component searches Google Drive files using provided credentials and query parameters.

For more on creating a service account JSON, see [Service Account JSON](https://developers.google.com/identity/protocols/oauth2/service-account).

### Inputs

| Input          | Type             | Description                                                                          |
| -------------- | ---------------- | ------------------------------------------------------------------------------------ |
| token_string   | SecretStrInput   | JSON string containing OAuth 2.0 access token information for service account access |
| query_item     | DropdownInput    | The field to query                                                                   |
| valid_operator | DropdownInput    | Operator to use in the query                                                         |
| search_term    | MessageTextInput | The value to search for in the specified query item                                  |
| query_string   | MessageTextInput | The query string used for searching (can be edited manually)                         |

### Outputs

| Output     | Type      | Description                                     |
| ---------- | --------- | ----------------------------------------------- |
| doc_urls   | List[str] | URLs of the found documents                     |
| doc_ids    | List[str] | IDs of the found documents                      |
| doc_titles | List[str] | Titles of the found documents                   |
| Data       | Data      | Document titles and URLs in a structured format |

## SQL Query

This component executes SQL queries on a specified database.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| query | Query | The SQL query to execute. |
| database_url | Database URL | The URL of the database. |
| include_columns | Include Columns | Include columns in the result. |
| passthrough | Passthrough | If an error occurs, return the query instead of raising an exception. |
| add_error | Add Error | Add the error to the result. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| result | Result | The result of the SQL query execution. |

## URL

This component fetches content from one or more URLs, processes the content, and returns it as a list of [Data](/concepts-objects) objects.

### Inputs

| Name | Display Name | Info                   |
| ---- | ------------ | ---------------------- |
| urls | URLs         | Enter one or more URLs |

### Outputs

| Name | Display Name | Info                                                         |
| ---- | ------------ | ------------------------------------------------------------ |
| data | Data         | List of Data objects containing fetched content and metadata |

## Webhook

This component defines a webhook trigger that runs a flow when it receives an HTTP POST request.

If the input is not valid JSON, the component wraps it in a `payload` object so that it can be processed and still trigger the flow. The component does not require an API key.

When a **Webhook** component is added to the workspace, a new **Webhook cURL** tab becomes available in the **API** pane that contains an HTTP POST request for triggering the webhook component. For example:

```bash
curl -X POST \
  "http://127.0.0.1:7860/api/v1/webhook/**YOUR_FLOW_ID**" \
  -H 'Content-Type: application/json'\
  -d '{"any": "data"}'
  ```

To test the webhook component:

1. Add a **Webhook** component to the flow.
2. Connect the **Webhook** component's **Data** output to the **Data** input of a [Data to Message](/components-processing#data-to-message) component.
3. Connect the **Data to Message** component's **Message** output to the **Text** input of a [Chat Output](/components-io#chat-output) component.
4. To send a POST request, copy the code from the **Webhook cURL** tab in the **API** pane and paste it into a terminal.
5. Send the POST request.
6. Open the **Playground**.
Your JSON data is posted to the **Chat Output** component, which indicates that the webhook component is correctly triggering the flow.

### Inputs

| Name | Type   | Description                                    |
| ---- | ------ | ---------------------------------------------- |
| data | String | JSON payload for testing the webhook component |

### Outputs

| Name        | Type | Description                           |
| ----------- | ---- | ------------------------------------- |
| output_data | Data | Processed data from the webhook input |
