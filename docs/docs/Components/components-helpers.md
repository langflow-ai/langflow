---
title: Helpers
slug: /components-helpers
---

# Helper components in Langflow

Helper components provide utility functions to help manage data, tasks, and other components in your flow.

## Use a helper component in a flow

Chat memory in Langflow is stored either in local Langflow tables with `LCBufferMemory`, or connected to an external database.

The **Store Message** helper component stores chat memories as [Data](/concepts-objects) objects, and the **Message History** helper component retrieves chat messages as data objects or strings.

This example flow stores and retrieves chat history from an [AstraDBChatMemory](/components-memories#astradbchatmemory-component) component with **Store Message** and **Chat Memory** components.

![Sample Flow storing Chat Memory in AstraDB](/img/astra_db_chat_memory_rounded.png)

## Batch Run Component

The Batch Run component runs a language model over each row of a [DataFrame](/concepts-objects#dataframe-object) text column and returns a new DataFrame with the original text and the model's response.

### Inputs

| Name | Display Name | Type | Info | Required |
|------|--------------|------|------|----------|
| model | Language Model | HandleInput | Connect the 'Language Model' output from your LLM component here. | Yes |
| system_message | System Message | MultilineInput | Multi-line system instruction for all rows in the DataFrame. | No |
| df | DataFrame | DataFrameInput | The DataFrame whose column (specified by 'column_name') will be treated as text messages. | Yes |
| column_name | Column Name | StrInput | The name of the DataFrame column to treat as text messages. Default='text'. | Yes |

### Outputs

| Name | Display Name | Method | Info |
|------|--------------|--------|------|
| batch_results | Batch Results | run_batch | A DataFrame with two columns: 'text_input' and 'model_response'. |

## Create List

This component dynamically creates a record with a specified number of fields.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| n_fields | Number of Fields | Number of fields to be added to the record. |
| text_key | Text Key | Key used as text. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| list | List | The dynamically created list with the specified number of fields. |

## Current date

The Current Date component returns the current date and time in a selected timezone. This component provides a flexible way to obtain timezone-specific date and time information within a Langflow pipeline.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|timezone|Timezone|Select the timezone for the current date and time.

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|current_date|Current Date|The resulting current date and time in the selected timezone.

## ID Generator

This component generates a unique ID.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| unique_id| Value | The generated unique ID. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| id | ID | The generated unique ID. |

## Message history

:::info
Prior to Langflow 1.1, this component was known as the Chat Memory component.
:::

This component retrieves and manages chat messages from Langflow tables or an external memory.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| memory | External Memory | Retrieve messages from an external memory. If empty, it will use the Langflow tables. |
| sender | Sender Type | Filter by sender type. |
| sender_name | Sender Name | Filter by sender name. |
| n_messages | Number of Messages | Number of messages to retrieve. |
| session_id | Session ID | The session ID of the chat. If empty, the current session ID parameter will be used. |
| order | Order | Order of the messages. |
| template | Template | The template to use for formatting the data. It can contain the keys `{text}`, `{sender}` or any other key in the message data. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| messages | Messages (Data) | Retrieved messages as Data objects. |
| messages_text | Messages (Text) | Retrieved messages formatted as text. |
| lc_memory | Memory | A constructed Langchain [ConversationBufferMemory](https://api.python.langchain.com/en/latest/memory/langchain.memory.buffer.ConversationBufferMemory.html) object  |

## Message store

This component stores chat messages or text into Langflow tables or an external memory.

It provides flexibility in managing message storage and retrieval within a chat system.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| message | Message | The chat message to be stored. (Required) |
| memory | External Memory | The external memory to store the message. If empty, it will use the Langflow tables. |
| sender | Sender | The sender of the message. Can be Machine or User. If empty, the current sender parameter will be used. |
| sender_name | Sender Name | The name of the sender. Can be AI or User. If empty, the current sender parameter will be used. |
| session_id | Session ID | The session ID of the chat. If empty, the current session ID parameter will be used. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| stored_messages | Stored Messages | The list of stored messages after the current message has been added. |

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

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| llm | Language Model | The language model to use to generate the structured output. |
| input_value | Input Message | The input message to the language model. |
| system_prompt | Format Instructions | Instructions to the language model for formatting the output. |
| schema_name | Schema Name | The name for the output data schema. |
| output_schema | Output Schema | Defines the structure and data types for the model's output.|
| multiple | Generate Multiple | [Deprecated] Always set to `True`. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| structured_output | Structured Output | The structured output is a Data object based on the defined schema. |
| structured_output_dataframe | DataFrame | The structured output converted to a [DataFrame](/concepts-objects#dataframe-object) format. |

