---
title: Processing
slug: /components-processing
---

import Icon from "@site/src/components/icon";

Processing components process and transform data within a flow.

## Use a processing component in a flow

The **Split Text** processing component in this flow splits the incoming [Data](/concepts-objects) into chunks to be embedded into the vector store component.

The component offers control over chunk size, overlap, and separator, which affect context and granularity in vector store retrieval results.

![](/img/vector-store-document-ingestion.png)

## Combine data

:::important
Prior to Langflow version 1.1.3, this component was named **Merge Data**.
:::

This component combines multiple data sources into a single unified [Data](/concepts-objects#data-object) object.

The component iterates through the input list of data objects, merging them into a single data object. If the input list is empty, it returns an empty data object. If there's only one input data object, it returns that object unchanged. The merging process uses the addition operator to combine data objects.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A list of data objects to be merged. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| merged_data | Merged Data | A single [Data](/concepts-objects#data-object) object containing the combined information from all input data objects. |

</details>

## DataFrame operations

This component performs operations on [DataFrame](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html) rows and columns.

To use this component in a flow, connect a component that outputs [DataFrame](/concepts-objects#dataframe-object) to the **DataFrame Operations** component.

This example fetches JSON data from an API. The **Lambda filter** component extracts and flattens the results into a tabular DataFrame. The **DataFrame Operations** component can then work with the retrieved data.

![Dataframe operations with flattened dataframe](/img/component-dataframe-operations.png)

1. The **API Request** component retrieves data with only `source` and `result` fields.
For this example, the desired data is nested within the `result` field.
2. Connect a **Lambda Filter** to the API request component, and a **Language model** to the **Lambda Filter**. This example connects a **Groq** model component.
3. In the **Groq** model component, add your **Groq** API key.
4. To filter the data, in the **Lambda filter** component, in the **Instructions** field, use natural language to describe how the data should be filtered.
For this example, enter:
```
I want to explode the result column out into a Data object
```
:::tip
Avoid punctuation in the **Instructions** field, as it can cause errors.
:::
5. To run the flow, in the **Lambda Filter** component, click <Icon name="Play" aria-label="Play icon" />.
6. To inspect the filtered data, in the **Lambda Filter** component, click <Icon name="TextSearch" aria-label="Inspect icon" />.
The result is a structured DataFrame.
```text
id | name             | company               | username        | email                              | address           | zip
---|------------------|----------------------|-----------------|------------------------------------|-------------------|-------
1  | Emily Johnson    | ABC Corporation      | emily_johnson   | emily.johnson@abccorporation.com   | 123 Main St       | 12345
2  | Michael Williams | XYZ Corp             | michael_williams| michael.williams@xyzcorp.com       | 456 Elm Ave       | 67890
```
7. Add the **DataFrame Operations** component, and a **Chat Output** component to the flow.
8. In the **DataFrame Operations** component, in the **Operation** field, select **Filter**.
9. To apply a filter, in the **Column Name** field, enter a column to filter on. This example filters by `name`.
10. Click **Playground**, and then click **Run Flow**.
The flow extracts the values from the `name` column.
```text
name
Emily Johnson
Michael Williams
John Smith
...
```

### Operations

This component can perform the following operations on Pandas [DataFrame](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html).

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

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| df | DataFrame | The input DataFrame to operate on. |
| operation | Operation | The DataFrame operation to perform. Options include Add Column, Drop Column, Filter, Head, Rename Column, Replace Value, Select Columns, Sort, and Tail. |
| column_name | Column Name | The column name to use for the operation. |
| filter_value | Filter Value | The value to filter rows by. |
| ascending | Sort Ascending | Whether to sort in ascending order. |
| new_column_name | New Column Name | The new column name when renaming or adding a column. |
| new_column_value | New Column Value | The value to populate the new column with. |
| columns_to_select | Columns to Select | A list of column names to select. |
| num_rows | Number of Rows | The number of rows to return for head/tail operations. The default is 5. |
| replace_value | Value to Replace | The value to replace in the column. |
| replacement_value | Replacement Value | The value to replace with. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output | DataFrame | The resulting DataFrame after the operation. |

</details>

## Data to DataFrame

This component converts one or multiple [Data](/concepts-objects#data-object) objects into a [DataFrame](/concepts-objects#dataframe-object). Each Data object corresponds to one row in the resulting DataFrame. Fields from the `.data` attribute become columns, and the `.text` field (if present) is placed in a 'text' column.

1. To use this component in a flow, connect a component that outputs [Data](/concepts-objects#data-object) to the **Data to Dataframe** component's input.
This example connects a **Webhook** component to convert `text` and `data` into a DataFrame.
2. To view the flow's output, connect a **Chat Output** component to the **Data to Dataframe** component.

![A webhook and data to dataframe](/img/component-data-to-dataframe.png)

3. Send a POST request to the **Webhook** containing your JSON data.
Replace `YOUR_FLOW_ID` with your flow ID.
This example uses the default Langflow server address.
```text
curl -X POST "http://127.0.0.1:7860/api/v1/webhook/YOUR_FLOW_ID" \
-H 'Content-Type: application/json' \
-d '{
    "text": "Alex Cruz - Employee Profile",
    "data": {
        "Name": "Alex Cruz",
        "Role": "Developer",
        "Department": "Engineering"
    }
}'
```

4. In the **Playground**, view the output of your flow.
The **Data to DataFrame** component converts the webhook request into a `DataFrame`, with `text` and `data` fields as columns.
```text
| text                         | data                                                                    |
|:-----------------------------|:------------------------------------------------------------------------|
| Alex Cruz - Employee Profile | {'Name': 'Alex Cruz', 'Role': 'Developer', 'Department': 'Engineering'} |
```

5. Send another employee data object.
```text
curl -X POST "http://127.0.0.1:7860/api/v1/webhook/YOUR_FLOW_ID" \
-H 'Content-Type: application/json' \
-d '{
    "text": "Kalani Smith - Employee Profile",
    "data": {
        "Name": "Kalani Smith",
        "Role": "Designer",
        "Department": "Design"
    }
}'
```

6. In the **Playground**, this request is also converted to `DataFrame`.
```text
| text                            | data                                                                 |
|:--------------------------------|:---------------------------------------------------------------------|
| Kalani Smith - Employee Profile | {'Name': 'Kalani Smith', 'Role': 'Designer', 'Department': 'Design'} |
```

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data_list | Data or Data List | One or multiple Data objects to transform into a DataFrame. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| dataframe | DataFrame | A DataFrame built from each Data object's fields plus a text column. |

</details>

## Filter data

:::important
This component is in **Beta** as of Langflow version 1.1.3, and is not yet fully supported.
:::

This component filters a [Data](/concepts-objects#data-object) object based on a list of keys.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The Data object to filter. |
| filter_criteria | Filter Criteria | A list of keys to filter by. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | A new Data object containing only the key-value pairs that match the filter criteria. |

</details>

## Filter values

:::important
This component is in **Beta** as of Langflow version 1.1.3, and is not yet fully supported.
:::

The Filter values component filters a list of data items based on a specified key, filter value, and comparison operator.

<details>
<summary>Parameters</summary>

**Inputs**
| Name | Display Name | Info |
|------|--------------|------|
| input_data | Input data | The list of data items to filter. |
| filter_key | Filter Key | The key to filter on. |
| filter_value | Filter Value | The value to filter by. |
| operator | Comparison Operator | The operator to apply for comparing the values. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered data | The resulting list of filtered data items. |

</details>

## Lambda filter

This component uses an LLM to generate a Lambda function for filtering or transforming structured data.

To use the **Lambda filter** component, you must connect it to a [Language Model](/components-models#language-model) component, which the component uses to generate a function based on the natural language instructions in the **Instructions** field.

This example gets JSON data from the `https://jsonplaceholder.typicode.com/users` API endpoint.
The **Instructions** field in the **Lambda filter** component specifies the task `extract emails`.
The connected LLM creates a filter based on the instructions, and successfully extracts a list of email addresses from the JSON data.

![](/img/component-lambda-filter.png)

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The structured data to filter or transform using a Lambda function. |
| llm | Language Model | The connection port for a [Model](/components-models) component. |
| filter_instruction | Instructions | The natural language instructions for how to filter or transform the data using a Lambda function, such as `Filter the data to only include items where the 'status' is 'active'`. |
| sample_size | Sample Size | For large datasets, the number of characters to sample from the dataset head and tail. |
| max_size | Max Size | The number of characters for the data to be considered "large", which triggers sampling by the `sample_size` value. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | The filtered or transformed [Data object](/concepts-objects#data-object). |
| dataframe | DataFrame | The filtered data as a [DataFrame](/concepts-objects#dataframe-object). |

</details>

## LLM router

This component routes requests to the most appropriate LLM based on OpenRouter model specifications.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| models | Language Models | A list of LLMs to route between. |
| input_value | Input | The input message to be routed. |
| judge_llm | Judge LLM | The LLM that evaluates and selects the most appropriate model. |
| optimization | Optimization | The optimization preference between quality, speed, cost, or balanced. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output | Output | The response from the selected model. |
| selected_model | Selected Model | The name of the chosen model. |

</details>

## Message to data

This component converts [Message](/concepts-objects#message-object) objects to [Data](/concepts-objects#data-object) objects.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| message | Message | The Message object to convert to a Data object. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The converted Data object. |

</details>

## Parser

This component formats `DataFrame` or `Data` objects into text using templates, with an option to convert inputs directly to strings using `stringify`.

To use this component, create variables for values in the `template` the same way you would in a [Prompt](/components-prompts) component. For `DataFrames`, use column names, for example `Name: {Name}`. For `Data` objects, use `{text}`.

To use the **Parser** component with a **Structured Output** component, do the following:

1. Connect a **Structured Output** component's **DataFrame** output to the **Parser** component's **DataFrame** input.
2. Connect the **File** component to the **Structured Output** component's **Message** input.
3. Connect the **OpenAI** model component's **Language Model** output to the **Structured Output** component's **Language Model** input.

The flow looks like this:

![A parser component connected to OpenAI and structured output](/img/component-parser.png)

4. In the **Structured Output** component, click **Open Table**.
This opens a pane for structuring your table.
The table contains the rows **Name**, **Description**, **Type**, and **Multiple**.
5. Create a table that maps to the data you're loading from the **File** loader.
For example, to create a table for employees, you might have the rows `id`, `name`, and `email`, all of type `string`.
6. In the **Template** field of the **Parser** component, enter a template for parsing the **Structured Output** component's DataFrame output into structured text.
Create variables for values in the `template` the same way you would in a [Prompt](/components-prompts) component.
For example, to present a table of employees in Markdown:
```text
# Employee Profile
## Personal Information
- **Name:** {name}
- **ID:** {id}
- **Email:** {email}
```
7. To run the flow, in the **Parser** component, click <Icon name="Play" aria-label="Play icon" />.
8. To view your parsed text, in the **Parser** component, click <Icon name="TextSearch" aria-label="Inspect icon" />.
9. Optionally, connect a **Chat Output** component, and open the **Playground** to see the output.

For an additional example of using the **Parser** component to format a DataFrame from a **Structured Output** component, see the **Market Research** template flow.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| mode | Mode | The tab selection between "Parser" and "Stringify" modes. "Stringify" converts input to a string instead of using a template. |
| pattern | Template | The template for formatting using variables in curly brackets. For DataFrames, use column names, such as `Name: {Name}`. For Data objects, use `{text}`. |
| input_data | Data or DataFrame | The input to parse. Accepts either a DataFrame or Data object. |
| sep | Separator | The string used to separate rows or items. The default is a newline. |
| clean_data | Clean Data | When stringify is enabled, this option cleans data by removing empty rows and lines. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| parsed_text | Parsed Text | The resulting formatted text as a [Message](/concepts-objects#message-object) object. |

</details>

## Regex extractor

This component extracts patterns from text using regular expressions. It can be used to find and extract specific patterns or information from text data.

To use this component in a flow:

1. Connect the **Regex Extractor** to a **URL** component and a **Chat Output** component.

![Regex extractor connected to url component](/img/component-url-regex.png)

2. In the **Regex Extractor** tool, enter a pattern to extract text from the **URL** component's raw output.
This example extracts the first paragraph from the "In the News" section of `https://en.wikipedia.org/wiki/Main_Page`:
```
In the news\s*\n(.*?)(?=\n\n)
```

Result:
```
Peruvian writer and Nobel Prize in Literature laureate Mario Vargas Llosa (pictured) dies at the age of 89.
```

## Save to File

This component saves [DataFrames, Data, or Messages](/concepts-objects) to various file formats.

1. To use this component in a flow, connect a component that outputs [DataFrames, Data, or Messages](/concepts-objects) to the **Save to File** component's input.
The following example connects a **Webhook** component to two **Save to File** components to demonstrate the different outputs.

![Two Save-to File components connected to a webhook](/img/component-save-to-file.png)

2. In the **Save to File** component's **Input Type** field, select the expected input type.
This example expects **Data** from the **Webhook**.
3. In the **File Format** field, select the file type for your saved file.
This example uses `.md` in one **Save to File** component, and `.xlsx` in another.
4. In the **File Path** field, enter the path for your saved file.
This example uses `./output/employees.xlsx` and `./output/employees.md` to save the files in a directory relative to where Langflow is running.
The component accepts both relative and absolute paths, and creates any necessary directories if they don't exist.
:::tip
If you enter a format in the `file_path` that is not accepted, the component appends the proper format to the file.
For example, if the selected `file_format` is `csv`, and you enter `file_path` as `./output/test.txt`, the file is saved as `./output/test.txt.csv` so the file is not corrupted.
:::
5. Send a POST request to the **Webhook** containing your JSON data.
Replace `YOUR_FLOW_ID` with your flow ID.
This example uses the default Langflow server address.
```text
curl -X POST "http://127.0.0.1:7860/api/v1/webhook/YOUR_FLOW_ID" \
-H 'Content-Type: application/json' \
-d '{
    "Name": ["Alex Cruz", "Kalani Smith", "Noam Johnson"],
    "Role": ["Developer", "Designer", "Manager"],
    "Department": ["Engineering", "Design", "Management"]
}'
```
6. In your local filesystem, open the `outputs` directory.
You should see two files created from the data you've sent: one in `.xlsx` for structured spreadsheets, and one in Markdown.
```text
| Name         | Role      | Department   |
|:-------------|:----------|:-------------|
| Alex Cruz    | Developer | Engineering  |
| Kalani Smith | Designer  | Design       |
| Noam Johnson | Manager   | Management   |
```

### File input format options

For `DataFrame` and `Data` inputs, the component can create:
  - `csv`
  - `excel`
  - `json`
  - `markdown`
  - `pdf`

For `Message` inputs, the component can create:
  - `txt`
  - `json`
  - `markdown`
  - `pdf`

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_text | Input Text | The text to analyze and extract patterns from. |
| pattern | Regex Pattern | The regular expression pattern to match in the text. |
| input_type | Input Type | The type of input to save. |
| df | DataFrame | The DataFrame to save. |
| data | Data | The Data object to save. |
| message | Message | The Message to save. |
| file_format | File Format | The file format to save the input in. |
| file_path | File Path | The full file path including filename and extension. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A list of extracted matches as Data objects. |
| text | Message | The extracted matches formatted as a Message object. |
| confirmation | Confirmation | The confirmation message after saving the file. |

</details>

## Split text

This component splits text into chunks based on specified criteria. It's ideal for chunking data to be tokenized and embedded into vector databases.

The **Split Text** component outputs **Chunks** or **DataFrame**.
The **Chunks** output returns a list of individual text chunks.
The **DataFrame** output returns a structured data format, with additional `text` and `metadata` columns applied.

1. To use this component in a flow, connect a component that outputs [Data or DataFrame](/concepts-objects) to the **Split Text** component's **Data** port.
This example uses the **URL** component, which is fetching JSON placeholder data.

![Split text component and chroma-db](/img/component-split-text.png)

2. In the **Split Text** component, define your data splitting parameters.

This example splits incoming JSON data at the separator `},`, so each chunk contains one JSON object.

The order of precedence is **Separator**, then **Chunk Size**, and then **Chunk Overlap**.
If any segment after separator splitting is longer than `chunk_size`, it is split again to fit within `chunk_size`.

After `chunk_size`, **Chunk Overlap** is applied between chunks to maintain context.

3. Connect a **Chat Output** component to the **Split Text** component's **DataFrame** output to view its output.
4. Click **Playground**, and then click **Run Flow**.
The output contains a table of JSON objects split at `},`.
```text
{
"userId": 1,
"id": 1,
"title": "Introduction to Artificial Intelligence",
"body": "Learn the basics of Artificial Intelligence and its applications in various industries.",
"link": "https://example.com/article1",
"comment_count": 8
},
{
"userId": 2,
"id": 2,
"title": "Web Development with React",
"body": "Build modern web applications using React.js and explore its powerful features.",
"link": "https://example.com/article2",
"comment_count": 12
},
```
5. Clear the **Separator** field, and then run the flow again.
Instead of JSON objects, the output contains 50-character lines of text with 10 characters of overlap.
```text
First chunk:  "title": "Introduction to Artificial Intelligence""
Second chunk: "elligence", "body": "Learn the basics of Artif"
Third chunk:  "s of Artificial Intelligence and its applications"
```

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data_inputs | Input Documents | The data to split. The component accepts [Data](/concepts-objects#data-object) or [DataFrame](/concepts-objects#dataframe-object) objects. |
| chunk_overlap | Chunk Overlap | The number of characters to overlap between chunks. Default: `200`. |
| chunk_size | Chunk Size | The maximum number of characters in each chunk. Default: `1000`. |
| separator | Separator | The character to split on. Default: `newline`. |
| text_key | Text Key | The key to use for the text column. Default: `text`. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| chunks | Chunks | A list of split text chunks as [Data](/concepts-objects#data-object) objects. |
| dataframe | DataFrame | A list of split text chunks as [DataFrame](/concepts-objects#dataframe-object) objects. |

</details>

## Update data

This component dynamically updates or appends data with specified fields.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| old_data | Data | The records to update. |
| number_of_fields | Number of Fields | The number of fields to add. The maximum is 15. |
| text_key | Text Key | The key for text content. |
| text_key_validator | Text Key Validator | Validates the text key presence. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The updated Data objects. |

</details>

## Legacy components

**Legacy** components are available for use but are no longer supported.

### Alter metadata

This component modifies metadata of input objects. It can add new metadata, update existing metadata, and remove specified metadata fields. The component works with both [Message](/concepts-objects#message-object) and [Data](/concepts-objects#data-object) objects, and can also create a new Data object from user-provided text.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Objects to which Metadata should be added |
| text_in | User Text | Text input; the value is contained in the 'text' attribute of the [Data](/concepts-objects#data-object) object. Empty text entries are ignored. |
| metadata | Metadata | Metadata to add to each object |
| remove_fields | Fields to Remove | Metadata fields to remove |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | List of Input objects, each with added metadata |

</details>

### Combine text

:::important
This component is in **Legacy**, which means it is no longer in active development.
Instead, use the [Combine data](#combine-data) component.
:::

This component concatenates two text sources into a single text chunk using a specified delimiter.

1. To use this component in a flow, connect two components that output [Messages](/concepts-objects#message-object) to the **Combine Text** component's **First Text** and **Second Text** inputs.
This example uses two **Text Input** components.

![Combine text component](/img/component-combine-text.png)

2. In the **Combine Text** component, in the **Text** fields of both **Text Input** components, enter some text to combine.
3. In the **Combine Text** component, enter an optional **Delimiter** value.
The delimiter character separates the combined texts.
This example uses `\n\n **end first text** \n\n **start second text** \n\n` to label the texts and create newlines between them.
4. Connect a **Chat Output** component to view the text combination.
5. Click **Playground**, and then click **Run Flow**.
The combined text appears in the **Playground**.
```text
This is the first text. Let's combine text!
end first text
start second text
Here's the second part. We'll see how combining text works.
```

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| first_text | First Text | The first text input to concatenate. |
| second_text | Second Text | The second text input to concatenate. |
| delimiter | Delimiter | A string used to separate the two text inputs. The default is a space. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| message | Message | A Message object containing the combined text. |

</details>

### Create data

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.1.3.
:::

This component dynamically creates a [Data](/concepts-objects#data-object) object with a specified number of fields.

<details>
<summary>Parameters</summary>

**Inputs**
| Name | Display Name | Info |
|------|--------------|------|
| number_of_fields | Number of Fields | The number of fields to be added to the record. |
| text_key | Text Key | Key that identifies the field to be used as the text content. |
| text_key_validator | Text Key Validator | If enabled, checks if the given `Text Key` is present in the given `Data`. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A [Data](/concepts-objects#data-object) object created with the specified fields and text key. |

</details>

### JSON cleaner

The JSON cleaner component cleans JSON strings to ensure they are fully compliant with the JSON specification.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| json_str | JSON String | The JSON string to be cleaned. This can be a raw, potentially malformed JSON string produced by language models or other sources that may not fully comply with JSON specifications. |
| remove_control_chars | Remove Control Characters | If set to True, this option removes control characters (ASCII characters 0-31 and 127) from the JSON string. This can help eliminate invisible characters that might cause parsing issues or make the JSON invalid. |
| normalize_unicode | Normalize Unicode | When enabled, this option normalizes Unicode characters in the JSON string to their canonical composition form (NFC). This ensures consistent representation of Unicode characters across different systems and prevents potential issues with character encoding. |
| validate_json | Validate JSON | If set to True, this option attempts to parse the JSON string to ensure it is well-formed before applying the final repair operation. It raises a ValueError if the JSON is invalid, allowing for early detection of major structural issues in the JSON. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output | Cleaned JSON String | The resulting cleaned, repaired, and validated JSON string that fully complies with the JSON specification. |

</details>

### Parse DataFrame

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.3.
Instead, use the [Parser](#parser) component.
:::

This component converts DataFrames into plain text using templates.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| df | DataFrame | The DataFrame to convert to text rows. |
| template | Template | Template for formatting (use `{column_name}` placeholders). |
| sep | Separator | String to join rows in output. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| text | Text | All rows combined into single text. |

</details>

### Parse JSON

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.1.3.
:::

This component converts and extracts JSON fields using JQ queries.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Data object to filter ([Message](/concepts-objects#message-object) or [Data](/concepts-objects#data-object)). |
| query | JQ Query | JQ Query to filter the data |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | Filtered data as list of [Data](/concepts-objects#data-object) objects. |

</details>

### Select data

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.1.3.
:::

This component selects a single [Data](/concepts-objects#data-object) item from a list.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data_list | Data List | List of data to select from |
| data_index | Data Index | Index of the data to select |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| selected_data | Selected Data | The selected [Data](/concepts-objects#data-object) object. |

</details>
