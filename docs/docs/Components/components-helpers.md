---
title: Helpers
slug: /components-helpers
---

import Icon from "@site/src/components/icon";

## Calculator

The Calculator component performs basic arithmetic operations on mathematical expressions. It supports addition, subtraction, multiplication, division, and exponentiation operations.

For an example of using this component in a flow, see the [Python interpreter](/components-processing#python-interpreter) component.

<details>
<summary>Parameters</summary>

| Name | Type | Description |
|------|------|-------------|
| expression | String | The arithmetic expression to evaluate, such as `4*4*(33/22)+12-20`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| result | Data | The calculation result as a Data object containing the evaluated expression. |

</details>

## Current date

The Current Date component returns the current date and time in a selected timezone. This component provides a flexible way to obtain timezone-specific date and time information within a Langflow pipeline.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| timezone | String | The timezone for the current date and time. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| current_date | String | The resulting current date and time in the selected timezone. |

</details>

## Message history

:::info
Prior to Langflow 1.5, this component was two separate components called **Chat History** and **Message Store**.
:::

This component combines the **Chat History** and **Message Store** component into one component that can utilize Langflow's SQLite database, or connect to external memory, to store and retrieve chat messages.

Chat memory is distinct from vector store memory, because it is built specifically for storing and retrieving chat messages from databases.

Memory components provide access to their respective external databases **as memory**. This allows Large Language Models (LLMs) or [agents](/agents) to access external memory for persistence and context retention.

In **Retrieve** mode, this component retrieves chat messages from Langflow tables or external memory.
In **Store** mode, this component stores chat messages in Langflow tables or external memory.

In this example, one **Message History** component stores the complete chat history in a local Langflow table, which the other **Message History** component retrieves as context for the LLM to answer each question.

![Message store and history components](/img/component-message-history-message-store.png)

To configure Langflow to store and retrieve messages from an external database instead of local Langflow memory, follow these steps.

1. Add two **Memory** components to your flow.
This example uses **Redit Chat Memory**.
2. To enable external memory ports, in both **Memory** components, click <Icon name="SlidersHorizontal" aria-hidden="true"/> **Controls**, and then enable **External Memory**.
3. Connect the **Memory** ports to the **Message History** components.
The flow looks like this:
![Message store and history components with external memory](/img/component-message-history-external-memory.png)
4. In the **Redis Chat Memory** components, add your connection information. These values are found in your Redis deployment. For more information, see the [Redis documentation](https://redis.io/docs/latest/).

For more information on configuring memory in Langflow, see [Memory](/memory).

<details>
<summary>Parameters</summary>

**Inputs**
| Name | Type | Description |
|------|------|-------------|
| memory | Memory | Retrieve messages from an external memory. If empty, the Langflow tables are used. |
| sender | String | Filter by sender type. |
| sender_name | String | Filter by sender name. |
| n_messages | Integer | The number of messages to retrieve. |
| session_id | String | The session ID of the chat. If empty, the current session ID parameter is used. |
| order | String | The order of the messages. |
| template | String | The template to use for formatting the data. It can contain the keys `{text}`, `{sender}` or any other key in the message data. |

**Outputs**
| Name | Type | Description |
|------|------|-------------|
| messages | Data | The retrieved messages as Data objects. |
| messages_text | Message | The retrieved messages formatted as text. |
| dataframe | DataFrame | A DataFrame containing the message data. |

</details>

## Legacy components

Legacy components are available for use but are no longer supported.

### Create List

This component dynamically creates a record with a specified number of fields.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| n_fields | Integer | The number of fields to be added to the record. |
| text_key | String | The key used as text. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| list | List | The dynamically created list with the specified number of fields. |

</details>

### ID Generator

This component generates a unique ID.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| unique_id | String | The generated unique ID. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| id | String | The generated unique ID. |

</details>

### Output Parser

This component transforms the output of a language model into a specified format. It supports CSV format parsing, which converts LLM responses into comma-separated lists using Langchain's `CommaSeparatedListOutputParser`.

:::note
This component only provides formatting instructions and parsing functionality. It does not include a prompt. You'll need to connect it to a separate Prompt component to create the actual prompt template for the LLM to use.
:::

Both the **Output Parser** and **Structured Output** components format LLM responses, but they have different use cases.
The **Output Parser** is simpler and focused on converting responses into comma-separated lists. Use this when you just need a list of items, for example `["item1", "item2", "item3"]`.
The **Structured Output** is more complex and flexible, and allows you to define custom schemas with multiple fields of different types. Use this when you need to extract structured data with specific fields and types.

To use this component:

1. Create a Prompt component and connect the Output Parser's `format_instructions` output to it. This ensures the LLM knows how to format its response.
2. Write your actual prompt text in the Prompt component, including the `{format_instructions}` variable.
For example, in your Prompt component, the template might look like:
```
{format_instructions}
Please list three fruits.
```
3. Connect the `output_parser` output to your LLM model.

4. The output parser converts this into a Python list: `["apple", "banana", "orange"]`.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| parser_type | String | The parser type. Currently supports "CSV". |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| format_instructions | String | Pass to a prompt template to include formatting instructions for LLM responses. |
| output_parser | Parser | The constructed output parser that can be used to parse LLM responses. |

</details>