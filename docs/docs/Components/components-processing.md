---
title: Processing
slug: /components-processing
---

# Processing components in Langflow

Processing components process and transform data within a flow.

## Use a processing component in a flow

The **Split Text** processing component in this flow splits the incoming [Data](/concepts-objects) into chunks to be embedded into the vector store component.

The component offers control over chunk size, overlap, and separator, which affect context and granularity in vector store retrieval results.

![](/img/vector-store-document-ingestion.png)

## Alter metadata

This component modifies metadata of input objects. It can add new metadata, update existing metadata, and remove specified metadata fields. The component works with both [Message](/concepts-objects#message-object) and [Data](/concepts-objects#data-object) objects, and can also create a new Data object from user-provided text.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Objects to which Metadata should be added |
| text_in | User Text | Text input; the value will be in the 'text' attribute of the [Data](/concepts-objects#data-object) object. Empty text entries are ignored. |
| metadata | Metadata | Metadata to add to each object |
| remove_fields | Fields to Remove | Metadata Fields to Remove |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | List of Input objects, each with added metadata |

## Combine text

This component concatenates two text sources into a single text chunk using a specified delimiter.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| first_text | First Text | The first text input to concatenate. |
| second_text | Second Text | The second text input to concatenate. |
| delimiter | Delimiter | A string used to separate the two text inputs. Defaults to a space. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|message |Message |A [Message](/concepts-objects#message-object) object containing the combined text.


## Create data

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.1.3.
:::

This component dynamically creates a [Data](/concepts-objects#data-object) object with a specified number of fields.

### Inputs
| Name | Display Name | Info |
|------|--------------|------|
| number_of_fields | Number of Fields | The number of fields to be added to the record. |
| text_key | Text Key | Key that identifies the field to be used as the text content. |
| text_key_validator | Text Key Validator | If enabled, checks if the given `Text Key` is present in the given `Data`. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A [Data](/concepts-objects#data-object) object created with the specified fields and text key. |

## Data combiner

:::important
Prior to Langflow version 1.1.3, this component was named **Merge Data**.
:::

This component combines multiple data sources into a single unified [Data](/concepts-objects#data-object) object.

The component iterates through the input list of data objects, merging them into a single data object. If the input list is empty, it returns an empty data object. If there's only one input data object, it returns that object unchanged. The merging process uses the addition operator to combine data objects.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A list of data objects to be merged. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| merged_data | Merged Data | A single [Data](/concepts-objects#data-object) object containing the combined information from all input data objects. |

## DataFrame operations

This component performs the following operations on Pandas [DataFrame](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html):

| Operation | Description | Required Inputs |
|-----------|-------------|-----------------|
| Add Column | Adds a new column with a constant value | new_column_name, new_column_value |
| Drop Column | Removes a specified column | column_name |
| Filter | Filters rows based on column value | column_name, filter_value |
| Head | Returns first n rows | num_rows |
| Rename Column | Renames an existing column | column_name, new_column_name |
| Replace Value | Replaces values in a column | column_name, replace_value, replacement_value |
| Select Columns | Selects specific columns | columns_to_select |
| Sort | Sorts DataFrame by column | column_name, ascending |
| Tail | Returns last n rows | num_rows |

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| df | DataFrame | The input DataFrame to operate on. |
| operation | Operation | Select the DataFrame operation to perform. Options: Add Column, Drop Column, Filter, Head, Rename Column, Replace Value, Select Columns, Sort, Tail |
| column_name | Column Name | The column name to use for the operation. |
| filter_value | Filter Value | The value to filter rows by. |
| ascending | Sort Ascending | Whether to sort in ascending order. |
| new_column_name | New Column Name | The new column name when renaming or adding a column. |
| new_column_value | New Column Value | The value to populate the new column with. |
| columns_to_select | Columns to Select | List of column names to select. |
| num_rows | Number of Rows | Number of rows to return (for head/tail). Default: 5 |
| replace_value | Value to Replace | The value to replace in the column. |
| replacement_value | Replacement Value | The value to replace with. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| output | DataFrame | The resulting DataFrame after the operation. |


## Data to message

:::important
Prior to Langflow version 1.1.3, this component was named **Parse Data**.
:::

The ParseData component converts data objects into plain text using a specified template.
This component transforms structured data into human-readable text formats, allowing for customizable output through the use of templates.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The data to convert to text. |
| template | Template | The template to use for formatting the data. It can contain the keys `{text}`, `{data}`, or any other key in the data. |
| sep | Separator | The separator to use between multiple data items. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| text | Text | The resulting formatted text string as a [Message](/concepts-objects#message-object) object. |

## Filter data

:::important
This component is in **Beta** as of Langflow version 1.1.3, and is not yet fully supported.
:::

This component filters a [Data](/concepts-objects#data-object) object based on a list of keys.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | Data object to filter. |
| filter_criteria | Filter Criteria | List of keys to filter by. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | A new [Data](/concepts-objects#data-object) object containing only the key-value pairs that match the filter criteria. |

## Filter values

:::important
This component is in **Beta** as of Langflow version 1.1.3, and is not yet fully supported.
:::

The Filter values component filters a list of data items based on a specified key, filter value, and comparison operator.

### Inputs
| Name | Display Name | Info |
|------|--------------|------|
| input_data | Input data | The list of data items to filter. |
| filter_key | Filter Key | The key to filter on, for example, 'route'. |
| filter_value | Filter Value | The value to filter by, for example, 'CMIP'. |
| operator | Comparison Operator | The operator to apply for comparing the values. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered data | The resulting list of filtered data items. |

## JSON cleaner

The JSON cleaner component cleans JSON strings to ensure they are fully compliant with the JSON specification.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| json_str | JSON String | The JSON string to be cleaned. This can be a raw, potentially malformed JSON string produced by language models or other sources that may not fully comply with JSON specifications. |
| remove_control_chars | Remove Control Characters | If set to True, this option removes control characters (ASCII characters 0-31 and 127) from the JSON string. This can help eliminate invisible characters that might cause parsing issues or make the JSON invalid. |
| normalize_unicode | Normalize Unicode | When enabled, this option normalizes Unicode characters in the JSON string to their canonical composition form (NFC). This ensures consistent representation of Unicode characters across different systems and prevents potential issues with character encoding. |
| validate_json | Validate JSON | If set to True, this option attempts to parse the JSON string to ensure it is well-formed before applying the final repair operation. It raises a ValueError if the JSON is invalid, allowing for early detection of major structural issues in the JSON. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| output | Cleaned JSON String | The resulting cleaned, repaired, and validated JSON string that fully complies with the JSON specification. |

## LLM router

This component routes requests to the most appropriate LLM based on OpenRouter model specifications.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| models | Language Models | List of LLMs to route between |
| input_value | Input | The input message to be routed |
| judge_llm | Judge LLM | LLM that will evaluate and select the most appropriate model |
| optimization | Optimization | Optimization preference (quality/speed/cost/balanced) |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| output | Output | The response from the selected model |
| selected_model | Selected Model | Name of the chosen model |


## Message to data

This component converts [Message](/concepts-objects#message-object) objects to [Data](/concepts-objects#data-object) objects.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| message | Message | The [Message](/concepts-objects#message-object) object to convert to a [Data](/concepts-objects#data-object) object. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The converted [Data](/concepts-objects#data-object) object. |


## Parse DataFrame

This component converts DataFrames into plain text using templates.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| df | DataFrame | The DataFrame to convert to text rows |
| template | Template | Template for formatting (use `{column_name}` placeholders) |
| sep | Separator | String to join rows in output |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| text | Text | All rows combined into single text |

## Parse JSON

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.1.3.
:::

This component converts and extracts JSON fields using JQ queries.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Data object to filter ([Message](/concepts-objects#message-object) or [Data](/concepts-objects#data-object)). |
| query | JQ Query | JQ Query to filter the data |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | Filtered data as list of [Data](/concepts-objects#data-object) objects. |

## Select data

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.1.3.
:::

This component selects a single [Data](/concepts-objects#data-object) item from a list.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data_list | Data List | List of data to select from |
| data_index | Data Index | Index of the data to select |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| selected_data | Selected Data | The selected [Data](/concepts-objects#data-object) object. |

## Split text

This component splits text into chunks based on specified criteria.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data_inputs | Input Documents | The data to split.The component accepts [Data](/concepts-objects#data-object) or [DataFrame](/concepts-objects#dataframe-object) objects. |
| chunk_overlap | Chunk Overlap | The number of characters to overlap between chunks. Default: `200`. |
| chunk_size | Chunk Size | The maximum number of characters in each chunk. Default: `1000`. |
| separator | Separator | The character to split on. Default: `newline`. |
| text_key | Text Key | The key to use for the text column (advanced). Default: `text`. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| chunks | Chunks | List of split text chunks as [Data](/concepts-objects#data-object) objects. |
| dataframe | DataFrame | List of split text chunks as [DataFrame](/concepts-objects#dataframe-object) objects. |

## Update data

This component dynamically updates or appends data with specified fields.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| old_data | Data | The records to update |
| number_of_fields | Number of Fields | Number of fields to add (max 15) |
| text_key | Text Key | Key for text content |
| text_key_validator | Text Key Validator | Validates text key presence |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | Updated [Data](/concepts-objects#data-object) objects. |
