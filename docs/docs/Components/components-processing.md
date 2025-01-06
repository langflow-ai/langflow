---
title: Processing
slug: /components-processing
---

# Processing components in Langflow

Processing components process and transform data within a flow.

## Use a processing component in a flow

The **Split Text** processing component in this flow splits the incoming [data](/configuration-objects) into chunks to be embedded into the vector store component.

The component offers control over chunk size, overlap, and separator, which affect context and granularity in vector store retrieval results.

![](/img/vector-store-document-ingestion.png)

## Combine Text

This component concatenates two text sources into a single text chunk using a specified delimiter.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| first_text | First Text | The first text input to concatenate. |
| second_text | Second Text | The second text input to concatenate. |
| delimiter | Delimiter | A string used to separate the two text inputs. Defaults to a space. |


## Filter Data

This component filters a Data object based on a list of keys.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | Data object to filter. |
| filter_criteria | Filter Criteria | List of keys to filter by. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | A new Data object containing only the key-value pairs that match the filter criteria. |


## Parse JSON

This component converts and extracts JSON fields using JQ queries.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Data object to filter. Can be a message or data object. |
| query | JQ Query | JQ Query to filter the data. The input is always a JSON list. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | Filtered data as a list of data objects. |

## Merge Data component

This component combines multiple data sources into a single unified Data object.

The component iterates through the input list of data objects, merging them into a single data object. If the input list is empty, it returns an empty data object. If there's only one input data object, it returns that object unchanged. The merging process uses the addition operator to combine data objects.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A list of data objects to be merged |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| merged_data | Merged Data | A single data object containing the combined information from all input data objects |


## Parse Data

The ParseData component converts data objects into plain text using a specified template.
This component transforms structured data into human-readable text formats, allowing for customizable output through the use of templates.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The data to convert to text. |
| template | Template | The template to use for formatting the data. It can contain the keys `{text}`, `{data}` or any other key in the data. |
| sep | Separator | The separator to use between multiple data items. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| text | Text | The resulting formatted text string as a message object. |


## Split Text

This component splits text into chunks of a specified length.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| texts | Texts | Texts to split. |
| separators | Separators | Characters to split on. Defaults to a space. |
| max_chunk_size | Max Chunk Size | The maximum length, in characters, of each chunk. |
| chunk_overlap | Chunk Overlap | The amount of character overlap between chunks. |
| recursive | Recursive | Whether to split recursively. |
