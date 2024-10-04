---
title: Helpers
sidebar_position: 4
slug: /components-helpers
---

# Helpers

Helper components provide utility functions to help manage data, tasks, and other components in your flow.

## Chat Memory

This component retrieves and manages chat messages from Langflow tables or an external memory.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| memory | External Memory | Retrieve messages from an external memory. If empty, it will use the Langflow tables. |
| sender | Sender Type | Filter by sender type. |
| sender_name | Sender Name | Filter by sender name. |
| n_messages | Number of Messages | Number of messages to retrieve. |
| session_id | Session ID | The session ID of the chat. If empty, the current session ID parameter will be used. |
| order | Order | Order of the messages. |
| template | Template | The template to use for formatting the data. It can contain the keys `{text}`, `{sender}` or any other key in the message data. |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| messages | Messages (Data) | Retrieved messages as Data objects. |
| messages_text | Messages (Text) | Retrieved messages formatted as text. |
| lc_memory | Memory | Built LangChain memory object. |

## Combine Text

This component concatenates two text sources into a single text chunk using a specified delimiter.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| first_text | First Text | The first text input to concatenate. |
| second_text | Second Text | The second text input to concatenate. |
| delimiter | Delimiter | A string used to separate the two text inputs. Defaults to a space. |

## Create List

This component dynamically creates a record with a specified number of fields.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| n_fields | Number of Fields | Number of fields to be added to the record. |
| text_key | Text Key | Key used as text. |

## Custom Component

Use this component as a template to create your custom component.

For more, see [Custom Components](components-custom-components).

## Filter Data

This component filters a Data object based on a list of keys.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | Data object to filter. |
| filter_criteria | Filter Criteria | List of keys to filter by. |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | A new Data object containing only the key-value pairs that match the filter criteria. |

## Hierarchical Task

This component creates and manages hierarchical tasks for CrewAI agents in a Playground environment.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Hierarchical/).

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| task_description | Description | Descriptive text detailing task's purpose and execution. |
| expected_output | Expected Output | Clear definition of expected task outcome. |
| tools | Tools | List of tools/resources limited for task execution. Uses the Agent tools by default. |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| task_output | Task | The built hierarchical task. |

## ID Generator

This component generates a unique ID.

### Parameters

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| value | Value | Unique ID generated. |

## Parse JSON

This component converts and extracts JSON fields using JQ queries.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| input_value | Input | Data object to filter. Can be a Message or Data object. |
| query | JQ Query | JQ Query to filter the data. The input is always a JSON list. |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| filtered_data | Filtered Data | Filtered data as a list of Data objects. |

## Merge Data

This component combines multiple data sources into a single unified Data object.

The component iterates through the input list of Data objects, merging them into a single Data object. If the input list is empty, it returns an empty Data object. If there's only one input Data object, it returns that object unchanged. The merging process uses the addition operator to combine Data objects.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | A list of Data objects to be merged |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| merged_data | Merged Data | A single Data object containing the combined information from all input Data objects |


## Parse Data

The ParseData component converts Data objects into plain text using a specified template.
This component transforms structured data into human-readable text formats, allowing for customizable output through the use of templates.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| data | Data | The data to convert to text |
| template | Template | The template to use for formatting the data. It can contain the keys `{text}`, `{data}` or any other key in the Data |
| sep | Separator | The separator to use between multiple data items |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| text | Text | The resulting formatted text string as a Message object |

## Sequential Task

This component creates and manage sequential tasks for CrewAI agents. It builds a SequentialTask object with the provided description, expected output, and agent, allowing for the specification of tools and asynchronous execution.

For more information, see the [CrewAI documentation](https://docs.crewai.com/how-to/Sequential/).

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| task_description | Description | Descriptive text detailing task's purpose and execution. |
| expected_output | Expected Output | Clear definition of expected task outcome. |
| tools | Tools | List of tools/resources limited for task execution. Uses the Agent tools by default. |
| agent | Agent | CrewAI Agent that will perform the task. |
| task | Task | CrewAI Task that will perform the task. |
| async_execution | Async Execution | Boolean flag indicating asynchronous task execution. |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| task_output | Task | The built sequential task or list of tasks. |

## Split Text

This component splits text into chunks of a specified length.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| texts | Texts | Texts to split. |
| separators | Separators | Characters to split on. Defaults to a space. |
| max_chunk_size | Max Chunk Size | The maximum length (in characters) of each chunk. |
| chunk_overlap | Chunk Overlap | The amount of character overlap between chunks. |
| recursive | Recursive | Whether to split recursively. |

## Store Message

This component stores chat messages or text into Langflow tables or an external memory.

It provides flexibility in managing message storage and retrieval within a chat system.

### Parameters

#### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| message | Message | The chat message to be stored. (Required) |
| memory | External Memory | The external memory to store the message. If empty, it will use the Langflow tables. |
| sender | Sender | The sender of the message. Can be Machine or User. If empty, the current sender parameter will be used. |
| sender_name | Sender Name | The name of the sender. Can be AI or User. If empty, the current sender parameter will be used. |
| session_id | Session ID | The session ID of the chat. If empty, the current session ID parameter will be used. |

#### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| stored_messages | Stored Messages | The list of stored messages after the current message has been added. |
