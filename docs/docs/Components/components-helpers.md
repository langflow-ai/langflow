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

## Create List

This component dynamically creates a record with a specified number of fields.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| n_fields | Number of Fields | Number of fields to be added to the record. |
| text_key | Text Key | Key used as text. |

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

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| value | Value | Unique ID generated. |

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

## Store Message

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

### Input

| Name | Display Name | Info |
|------|--------------|------|
| llm | Language Model | The language model to use to generate the structured output. |
| input_value | Input message | The input message for the language model to process. |
| schema_name | Schema Name | Provide a name for the output data schema. |
| output_schema | Output Schema | Define the structure and data types for the model's output. |
| multiple | Generate Multiple | Set to True if the model should generate a list of outputs instead of a single output. |

### Output

| structured_output | Structured Output | The resulting structured output based on the defined schema. |
