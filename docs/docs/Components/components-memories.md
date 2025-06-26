---
title: Memories
slug: /components-memories
---

# Memory components in Langflow

Memory components store and retrieve chat messages by [`session_id`](/session-id).

They are distinct from vector store components, because they are built specifically for storing and retrieving chat messages from external databases.

Memory components provide access to their respective external databases **as memory**. This allows Large Language Models (LLMs) or [agents](/components-agents) to access external memory for persistence and context retention.

## Use a memory component in a flow

This example flow stores and retrieves chat history from an **Astra DB Chat Memory** component with **Store Message** and **Message history** components.

The **Store Message** helper component stores chat memories as [Data](/concepts-objects) objects, and the **Message History** helper component retrieves chat messages as [Data](/concepts-objects) objects or strings.

![Sample Flow storing Message history in AstraDB](/img/astra_db_chat_memory_rounded.png)

## AstraDBChatMemory Component

This component creates an `AstraDBChatMessageHistory` instance, which stores and retrieves chat messages using Astra DB, a cloud-native database service.

<details>
<summary>Parameters</summary>

**Inputs**

| Name             | Type          | Description                                                           |
|------------------|---------------|-----------------------------------------------------------------------|
| collection_name  | String        | The name of the Astra DB collection for storing messages. Required. |
| token            | SecretString  | The authentication token for Astra DB access. Required. |
| api_endpoint     | SecretString  | The API endpoint URL for the Astra DB service. Required. |
| namespace        | String        | The optional namespace within Astra DB for the collection. |
| session_id       | MessageText   | The unique identifier for the chat session. Uses the current session ID if not provided. |

**Outputs**

| Name            | Type                    | Description                                               |
|-----------------|-------------------------|-----------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of AstraDBChatMessageHistory for the session. |

</details>

## CassandraChatMemory Component

This component creates a `CassandraChatMessageHistory` instance, enabling storage and retrieval of chat messages using Apache Cassandra or DataStax Astra DB.

<details>
<summary>Parameters</summary>

**Inputs**

| Name           | Type          | Description                                                                   |
|----------------|---------------|-------------------------------------------------------------------------------|
| database_ref   | MessageText   | The contact points for the Cassandra database or Astra DB database ID. Required. |
| username       | MessageText   | The username for Cassandra. Leave empty for Astra DB. |
| token          | SecretString  | The password for Cassandra or the token for Astra DB. Required. |
| keyspace       | MessageText   | The keyspace in Cassandra or namespace in Astra DB. Required. |
| table_name     | MessageText   | The name of the table or collection for storing messages. Required. |
| session_id     | MessageText   | The unique identifier for the chat session. Optional. |
| cluster_kwargs | Dictionary    | Additional keyword arguments for the Cassandra cluster configuration. Optional. |

**Outputs**

| Name            | Type                    | Description                                                  |
|-----------------|-------------------------|--------------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of CassandraChatMessageHistory for the session. |

</details>

## GridGainChatMemory Component

This component creates a chat message history using GridGain, enabling storage and retrieval of chat messages using GridGain's distributed caching capabilities.

### Inputs

| Name         | Type          | Description                                                           |
|--------------|---------------|-----------------------------------------------------------------------|
| host         | String        | GridGain server host address. Required. Default value: "localhost".        |
| port         | String        | GridGain server port number. Required. Default value: "10800".            |
| cache_name   | String        | Name of the GridGain cache that is used to store messages. Required. Default value: "langchain_message_store" |
| session_id   | MessageText   | Chat session ID. Uses current session ID if not provided.             |
| client_type  | String        | Type of client to use. Required. Default value: "pygridgain".                     |


### Outputs

| Name            | Type                    | Description                                               |
|-----------------|-------------------------|-----------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of GridGainChatMessageHistory for the session. |

## Mem0 Chat Memory

The Mem0 Chat Memory component retrieves and stores chat messages using Mem0 memory storage.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| mem0_config | Mem0 Configuration | The configuration dictionary for initializing the Mem0 memory instance. |
| ingest_message | Message to Ingest | The message content to be ingested into Mem0 memory. |
| existing_memory | Existing Memory Instance | An optional existing Mem0 memory instance. |
| user_id | User ID | The identifier for the user associated with the messages. |
| search_query | Search Query | The input text for searching related memories in Mem0. |
| mem0_api_key | Mem0 API Key | The API key for the Mem0 platform. Leave empty to use the local version. |
| metadata | Metadata | The additional metadata to associate with the ingested message. |
| openai_api_key | OpenAI API Key | The API key for OpenAI. Required when using OpenAI embeddings without a provided configuration. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| memory | Mem0 Memory | The resulting Mem0 Memory object after ingesting data. |
| search_results | Search Results | The search results from querying Mem0 memory. |

</details>

## Redis Chat Memory

This component retrieves and stores chat messages from Redis.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| host | hostname | The IP address or hostname. |
| port | port | The Redis Port Number. |
| database | database | The Redis database. |
| username | Username | The Redis username. |
| password | Password | The password for the username. |
| key_prefix | Key prefix | The key prefix. |
| session_id | Session ID | The unique session identifier for the message. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| memory | Memory | The Redis chat message history object. |

</details>

## Legacy components

**Legacy** components are available for use but are no longer supported.

### ZepChatMemory Component

This component creates a `ZepChatMessageHistory` instance, enabling storage and retrieval of chat messages using Zep, a memory server for Large Language Models (LLMs).

<details>
<summary>Parameters</summary>

**Inputs**

| Name          | Type          | Description                                               |
|---------------|---------------|-----------------------------------------------------------|
| url           | MessageText   | The URL of the Zep instance. Required. |
| api_key       | SecretString  | The API Key for authentication with the Zep instance. |
| api_base_path | Dropdown      | The API version to use. Options include api/v1 or api/v2. |
| session_id    | MessageText   | The unique identifier for the chat session. Optional. |

**Outputs**

| Name            | Type                    | Description                                           |
|-----------------|-------------------------|-------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of ZepChatMessageHistory for the session. |

</details>