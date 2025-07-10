---
title: Processing
slug: /components-processing
---

import Icon from "@site/src/components/icon";

Processing components process and transform data within a flow, like converting `Data` to text with a [Parser](#parser) component, filtering data with natural language with the [Smart function](#smart-function), or saving data to your local machine with [Save File](#save-file).

## Batch Run

The **Batch Run** component runs a language model over **each row** of a [DataFrame](/concepts-objects#dataframe-object) text column and returns a new DataFrame with the original text and an LLM response.

The response contains the following columns:

* `text_input`: The original text from the input DataFrame.
* `model_response`: The model's response for each input.
* `batch_index`: The processing order, with a `0`-based index.
* `metadata` (optional): Additional information about the processing.

These columns, when connected to a **Parser** component, can be used as variables within curly braces.

To use the Batch Run component with a **Parser** component, do the following:

1. Connect a **Model** component to the **Batch Run** component's **Language model** port.
2. Connect a component that outputs DataFrame, like **File** component, to the **Batch Run** component's **DataFrame** input.
3. Connect the **Batch Run** component's **Batch Results** output to a **Parser** component's **DataFrame** input.
The flow looks like this:

![A batch run component connected to OpenAI and a Parser](/img/component-batch-run.png)

4. In the **Column Name** field of the **Batch Run** component, enter a column name based on the data you're loading from the **File** loader. For example, to process a column of `name`, enter `name`.
5. Optionally, in the **System Message** field of the **Batch Run** component, enter a **System Message** to instruct the connected LLM on how to process your file. For example, `Create a business card for each name.`
6. In the **Template** field of the **Parser** component, enter a template for using the **Batch Run** component's new DataFrame columns.
To use all three columns from the **Batch Run** component, include them like this:
```text
record_number: {batch_index}, name: {text_input}, summary: {model_response}
```
7. To run the flow, in the **Parser** component, click <Icon name="Play" aria-hidden="True" /> **Run component**.
8. To view your created DataFrame, in the **Parser** component, click <Icon name="TextSearch" aria-hidden="True" /> **Inspect output**.
9. Optionally, connect a **Chat Output** component, and open the **Playground** to see the output.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model | HandleInput | Connect the 'Language Model' output from your LLM component here. Required. |
| system_message | MultilineInput | A multi-line system instruction for all rows in the DataFrame. |
| df | DataFrameInput | The DataFrame whose column is treated as text messages, as specified by 'column_name'. Required. |
| column_name | MessageTextInput | The name of the DataFrame column to treat as text messages. If empty, all columns are formatted in TOML. |
| output_column_name | MessageTextInput | Name of the column where the model's response is stored. Default=`model_response`. |
| enable_metadata | BoolInput | If True, add metadata to the output DataFrame. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| batch_results | DataFrame | A DataFrame with all original columns plus the model's response column. |

</details>

## Data operations

This component performs operations on [Data](/concepts-objects#data-object) objects, including selecting keys, evaluating literals, combining data, filtering values, appending/updating data, removing keys, and renaming keys.

1. To use this component in a flow, connect a component that outputs [Data](/concepts-objects#data-object) to the **Data Operations** component's input.
All operations in the component require at least one [Data](/concepts-objects#data-object) input.
2. In the **Operations** field, select the operation you want to perform.
For example, send this request to the **Webhook** component.
Replace `YOUR_FLOW_ID` with your flow ID.
    ```bash
    curl -X POST "http://127.0.0.1:7860/api/v1/webhook/YOUR_FLOW_ID" \
    -H 'Content-Type: application/json' \
    -d '{
      "id": 1,
      "name": "Leanne Graham",
      "username": "Bret",
      "email": "Sincere@april.biz",
      "address": {
        "street": "Kulas Light",
        "suite": "Apt. 556",
        "city": "Gwenborough",
        "zipcode": "92998-3874",
        "geo": {
          "lat": "-37.3159",
          "lng": "81.1496"
        }
      },
      "phone": "1-770-736-8031 x56442",
      "website": "hildegard.org",
      "company": {
        "name": "Romaguera-Crona",
        "catchPhrase": "Multi-layered client-server neural-net",
        "bs": "harness real-time e-markets"
      }
    }'
    ```

3. In the **Data Operations** component, select the **Select Keys** operation to extract specific user information.
To add additional keys, click <Icon name="Plus" aria-hidden="True" /> **Add more**.
![A webhook and data operations component](/img/component-data-operations-select-key.png)
4. Filter by `name`, `username`, and `email` to select the values from the request.
    ```json
    {
      "name": "Leanne Graham",
      "username": "Bret",
      "email": "Sincere@april.biz"
    }
    ```

### Operations

The component supports the following operations.
All operations in the **Data operations** component require at least one [Data](/concepts-objects#data-object) input.

| Operation | Required Inputs | Info |
|-----------|----------------|-------------|
| Select Keys | `select_keys_input` | Selects specific keys from the data. |
| Literal Eval | None | Evaluates string values as Python literals. |
| Combine | None | Combines multiple data objects into one. |
| Filter Values | `filter_key`, `filter_values`, `operator` | Filters data based on key-value pair. |
| Append or Update | `append_update_data` | Adds or updates key-value pairs. |
| Remove Keys | `remove_keys_input` | Removes specified keys from the data. |
| Rename Keys | `rename_keys_input` | Renames keys in the data. |

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The [Data](/concepts-objects#data-object) object to operate on. |
| operations | Operations | The operation to perform on the data. |
| select_keys_input | Select Keys | A list of keys to select from the data. |
| filter_key | Filter Key | The key to filter by. |
| operator | Comparison Operator | The operator to apply for comparing values. |
| filter_values | Filter Values | A list of values to filter by. |
| append_update_data | Append or Update | The data to append or update the existing data with. |
| remove_keys_input | Remove Keys | A list of keys to remove from the data. |
| rename_keys_input | Rename Keys | A list of keys to rename in the data. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data_output | Data | The resulting Data object after the operation. |

</details>

## DataFrame operations

This component performs operations on [DataFrame](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html) rows and columns.

To use this component in a flow, connect a component that outputs [DataFrame](/concepts-objects#dataframe-object) to the **DataFrame Operations** component.

This example fetches JSON data from an API. The **Smart Filter** component extracts and flattens the results into a tabular DataFrame. The **DataFrame Operations** component can then work with the retrieved data.

![Dataframe operations with flattened dataframe](/img/component-dataframe-operations.png)

1. The **API Request** component retrieves data with only `source` and `result` fields.
For this example, the desired data is nested within the `result` field.
2. Connect a **Smart Filter** to the API request component, and a **Language model** to the **Smart Filter**. This example connects a **Groq** model component.
3. In the **Groq** model component, add your **Groq** API key.
4. To filter the data, in the **Smart filter** component, in the **Instructions** field, use natural language to describe how the data should be filtered.
For this example, enter:
```
I want to explode the result column out into a Data object
```
:::tip
Avoid punctuation in the **Instructions** field, as it can cause errors.
:::
5. To run the flow, in the **Smart Filter** component, click <Icon name="Play" aria-hidden="true" /> **Run component**.
6. To inspect the filtered data, in the **Smart Filter** component, click <Icon name="TextSearch" aria-hidden="true" /> **Inspect output**.
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

| Operation | Required Inputs | Info |
|-----------|----------------|-------------|
| Add Column | new_column_name, new_column_value | Adds a new column with a constant value. |
| Drop Column | column_name | Removes a specified column. |
| Filter | column_name, filter_value | Filters rows based on column value. |
| Head | num_rows | Returns first `n` rows. |
| Rename Column | column_name, new_column_name | Renames an existing column. |
| Replace Value | column_name, replace_value, replacement_value | Replaces values in a column. |
| Select Columns | columns_to_select | Selects specific columns. |
| Sort | column_name, ascending | Sorts DataFrame by column. |
| Tail | num_rows | Returns last `n` rows. |

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

## LLM router

This component routes requests to the most appropriate LLM based on [OpenRouter](https://openrouter.ai/docs/quickstart) model specifications.

The judge LLM analyzed your input message to understand the evaluation context, and then selects the most appropriate model from your LLM pool.

The selected model processes your input and returns the response.

To use the **LLM Router** component in a flow, do the following:

1. Connect multiple **Language Model** components to the **LLM Router**'s **Language Models** input.

2. Connect a **Judge LLM** component to the **Judge LLM** input.

3. Connect **Chat Input** and **Chat Output** components to the **LLM Router**.
The flow looks like this:

![LLM router component](/img/component-llm-router.png)

4. In the LLM Router component, set your **Optimization** preference:
   - **Quality**: Prioritizes the highest quality response.
   - **Speed**: Prioritizes the fastest response time.
   - **Cost**: Prioritizes the most cost-effective option.
   - **Balanced**: Strikes a balance between quality, speed, and cost.

5. Run the flow.
Your input is the task that the LLM router evaluates the models against, such as `Write a story about horses` or `How do I parse data objects out of JSON?`.
6. In the LLM Router component, select the **Model Selection Decision** output to view the router's reasoning.

    ```text
    Model Selection Decision:
    - Selected Model Index: 0
    - Selected Langflow Model Name: gpt-4o-mini
    - Selected API Model ID (if resolved): openai/gpt-4o-mini
    - Optimization Preference: cost
    - Input Query Length: 27 characters (~5 tokens)
    - Number of Models Considered: 2
    - Specifications Source: OpenRouter API
    ```

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
7. To run the flow, in the **Parser** component, click <Icon name="Play" aria-hidden="true"/> **Run component**.
8. To view your parsed text, in the **Parser** component, click <Icon name="TextSearch" aria-hidden="true"/> **Inspect output**.
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

## Python interpreter

This component allows you to execute Python code with imported packages.

1. To use this component in a flow,in the **Global Imports** field, add the packages you want to import as a comma-separated list, such as `math,pandas`.
At least one import is required.
2. In the **Python Code** field, enter the Python code you want to execute. Use `print()` to see the output.
3. Optionally, enable **Tool Mode** and connect the interpreter to an **Agent** as a tool.
For example, connect a **Python Interpreter** and a [Calculator](/components-helpers#calculator) as tools for an Agent, and test how it chooses different tools to solve math problems.
The flow looks like this:
![Python Interpreter and calculator connected to Agent](/img/component-python-interpreter.png)
4. Ask the agent an easier math question.
The **Calculator** tool can add, subtract, multiple, divide, or perform exponentiation.
The agent executes the `evaluate_expression` tool to correctly answer the question.

Result:
```text
Executed evaluate_expression
Input:
{
  "expression": "2+5"
}
Output:
{
  "result": "7"
}
```

5. Give the agent complete Python code.
This example creates a Pandas DataFrame table with the imported `pandas` packages, and returns the square root of the mean squares.

```python
import pandas as pd
import math

# Create a simple DataFrame
df = pd.DataFrame({
    'numbers': [1, 2, 3, 4, 5],
    'squares': [x**2 for x in range(1, 6)]
})

# Calculate the square root of the mean
result = math.sqrt(df['squares'].mean())
print(f"Square root of mean squares: {result}")
```

The Agent correctly chooses the `run_python_repl` tool to solve the problem.

Result:
```text
Executed run_python_repl

Input:

{
  "python_code": "import pandas as pd\nimport math\n\n# Create a simple DataFrame\ndf = pd.DataFrame({\n    'numbers': [1, 2, 3, 4, 5],\n    'squares': [x**2 for x in range(1, 6)]\n})\n\n# Calculate the square root of the mean\nresult = math.sqrt(df['squares'].mean())\nprint(f\"Square root of mean squares: {result}\")"
}
Output:

{
  "result": "Square root of mean squares: 3.3166247903554"
}
```

If you don't include the package imports in the chat, the Agent can still create the table using `pd.DataFrame`, because the `pandas` package is imported globally by the Python interpreter component in the **Global Imports** field.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| global_imports | String | A comma-separated list of modules to import globally, such as `math,pandas,numpy`. |
| python_code | Code | The Python code to execute. Only modules specified in Global Imports can be used. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| results | Data | The output of the executed Python code, including any printed results or errors. |

</details>

## Save file

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

## Smart function

:::tip
Prior to Langflow 1.5, this component was named the Lambda filter.
:::

This component uses an LLM to generate a function for filtering or transforming structured data.

To use the **Smart function** component, you must connect it to a [Language Model](/components-models) component, which the component uses to generate a function based on the natural language instructions in the **Instructions** field.

This example gets JSON data from the `https://jsonplaceholder.typicode.com/users` API endpoint.
The **Instructions** field in the **Smart function** component specifies the task `extract emails`.
The connected LLM creates a filter based on the instructions, and successfully extracts a list of email addresses from the JSON data.

![Smart function connected to an LLM](/img/component-lambda-filter.png)

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

## Structured output

This component transforms LLM responses into structured data formats.

In this example from the **Financial Support Parser** template, the **Structured Output** component transforms unstructured financial reports into structured data.

![Structured output example](/img/component-structured-output.png)

The connected LLM model is prompted by the **Structured Output** component's `Format Instructions` parameter to extract structured output from the unstructured text. `Format Instructions` is utilized as the system prompt for the **Structured Output** component.

In the **Structured Output** component, click the **Open table** button to view the `Output Schema` table.
The `Output Schema` parameter defines the structure and data types for the model's output using a table with the following fields:

* **Name**: The name of the output field.
* **Description**: The purpose of the output field.
* **Type**: The data type of the output field. The available types are `str`, `int`, `float`, `bool`, `list`, or `dict`. The default is `text`.
* **Multiple**: This feature is deprecated. Currently, it is set to `True` by default if you expect multiple values for a single field. For example, a `list` of `features` is set to `True` to contain multiple values, such as `["waterproof", "durable", "lightweight"]`. Default: `True`.

The **Parse DataFrame** component parses the structured output into a template for orderly presentation in chat output. The template receives the values from the `output_schema` table with curly braces.

For example, the template `EBITDA: {EBITDA}  ,  Net Income: {NET_INCOME} , GROSS_PROFIT: {GROSS_PROFIT}` presents the extracted values in the **Playground** as `EBITDA: 900 million , Net Income: 500 million , GROSS_PROFIT: 1.2 billion`.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use to generate the structured output. |
| input_value | String | The input message to the language model. |
| system_prompt | String | The instructions to the language model for formatting the output. |
| schema_name | String | The name for the output data schema. |
| output_schema | Table | The structure and data types for the model's output. |
| multiple | Boolean | [Deprecated] Always set to `True`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| structured_output | Data | The structured output is a Data object based on the defined schema. |

</details>

## Type convert

This component converts data types between different formats. It can transform data between [Data](/concepts-objects#data-object), [DataFrame](/concepts-objects#dataframe-object), and [Message](/concepts-objects#message-object) objects.

* **Data**: A structured object that contains both text and metadata.
```json
{
  "text": "User Profile",
  "data": {
    "name": "John Smith",
    "age": 30,
    "email": "john@example.com"
  }
}
```
* **DataFrame**: A tabular data structure with rows and columns.
Keys are columns, and each dictionary (a collection of key-value pairs) in the list is a row.
```json
[
  {
    "name": "John Smith",
    "age": 30,
    "email": "john@example.com"
  },
  {
    "name": "Jane Doe",
    "age": 25,
    "email": "jane@example.com"
  }
]
```
* **Message**: A string, such as`"Name: John Smith, Age: 30, Email: john@example.com"`.

To use this component in a flow, do the following:

1. Add the **Web search** component to the [Basic prompting](/basic-prompting) flow. In the **Search Query** field, enter a query, such as `environmental news`.
2. Connect the **Web search** component's output to a component that accepts the DataFrame input.
This example uses a **Prompt** component to give the chatbot context, so you must convert the **Web search** component's DataFrame output to a Message type.
3. Connect a **Type Convert** component to convert the DataFrame to a Message.
4. In the **Type Convert** component, in the **Output Type** field, select **Message**.
Your flow looks like this:

![Type convert web search output to chat](/img/component-type-convert-and-web-search.png)

5. In the **Language Model** component, in the **OpenAI API Key** field, add your OpenAI API key.
6. Click **Playground**, and then ask about `latest news`.

The search results are returned to the Playground as a message.

Result:
```text
Latest news
AI
gpt-4o-mini
Here are some of the latest news articles related to the environment:
Ozone Pollution and Global Warming: A recent study highlights that ozone pollution is a significant global environmental concern, threatening human health and crop production while exacerbating global warming. Read more
...
```

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_data | Input Data | The data to convert. Accepts Data, DataFrame, or Message objects. |
| output_type | Output Type | The desired output type. Options: Data, DataFrame, or Message. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output | Output | The converted data in the specified format. |

</details>

## Legacy components

**Legacy** components are available for use but are no longer supported.

### Alter metadata

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
Instead, use the [Data operations](#data-operations) component.
:::

This component modifies metadata of input objects. It can add new metadata, update existing metadata, and remove specified metadata fields. The component works with both [Message](/concepts-objects#message-object) and [Data](/concepts-objects#data-object) objects, and can also create a new Data object from user-provided text.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Objects to which Metadata should be added. |
| text_in | User Text | Text input; the value is contained in the 'text' attribute of the [Data](/concepts-objects#data-object) object. Empty text entries are ignored. |
| metadata | Metadata | Metadata to add to each object. |
| remove_fields | Fields to Remove | Metadata fields to remove. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | List of Input objects, each with added metadata. |

</details>

### Combine data

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
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


### Combine text

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
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
This component is in **Legacy**, which means it is available for use but no longer in active development.
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

### Data to DataFrame

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
:::
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

### Filter data

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
Instead, use the [Data operations](#data-operations) component.
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

### Filter values

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
Instead, use the [Data operations](#data-operations) component.
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

### JSON cleaner

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
:::

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

### Message to data

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

### Parse DataFrame

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
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
This component is in **Legacy**, which means it is available for use but no longer in active development.
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

### Regex extractor

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
:::

This component extracts patterns from text using regular expressions. It can be used to find and extract specific patterns or information from text data.

To use this component in a flow:

1. Connect the **Regex Extractor** to a **URL** component and a **Chat Output** component.

2. In the **Regex Extractor** tool, enter a pattern to extract text from the **URL** component's raw output.
This example extracts the first paragraph from the "In the News" section of `https://en.wikipedia.org/wiki/Main_Page`:
```
In the news\s*\n(.*?)(?=\n\n)
```

Result:
```
Peruvian writer and Nobel Prize in Literature laureate Mario Vargas Llosa (pictured) dies at the age of 89.
```

### Select data

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
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

### Update data

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
:::

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

