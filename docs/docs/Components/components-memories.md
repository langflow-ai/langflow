---
title: Memories
slug: /components-memories
---

# Memory components in Langflow

Memory components store and retrieve chat messages by `session_id`.

They are distinct from vector store components, because they are built specifically for storing and retrieving chat messages from external databases.

Memory components provide access to their respective external databases **as memory**. This allows Large Language Models (LLMs) or [agents](/components-agents) to access external memory for persistence and context retention.

## Use a memory component in a flow

This example flow stores and retrieves chat history from an **Astra DB Chat Memory** component with **Store Message** and **Chat Memory** components.

The **Store Message** helper component stores chat memories as [Data](/concepts-objects) objects, and the **Message History** helper component retrieves chat messages as [Data](/concepts-objects) objects or strings.

![Sample Flow storing Chat Memory in AstraDB](/img/astra_db_chat_memory_rounded.png)

## AstraDBChatMemory Component

This component creates an `AstraDBChatMessageHistory` instance, which stores and retrieves chat messages using Astra DB, a cloud-native database service.

### Inputs

| Name             | Type          | Description                                                           |
|------------------|---------------|-----------------------------------------------------------------------|
| collection_name  | String        | Name of the Astra DB collection for storing messages. Required.       |
| token            | SecretString  | Authentication token for Astra DB access. Required.                   |
| api_endpoint     | SecretString  | API endpoint URL for the Astra DB service. Required.                  |
| namespace        | String        | Optional namespace within Astra DB for the collection.                |
| session_id       | MessageText   | Chat session ID. Uses current session ID if not provided.             |

### Outputs

| Name            | Type                    | Description                                               |
|-----------------|-------------------------|-----------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of AstraDBChatMessageHistory for the session. |

## CassandraChatMemory Component

This component creates a `CassandraChatMessageHistory` instance, enabling storage and retrieval of chat messages using Apache Cassandra or DataStax Astra DB.

### Inputs

| Name           | Type          | Description                                                                   |
|----------------|---------------|-------------------------------------------------------------------------------|
| database_ref   | MessageText   | Contact points for Cassandra or Astra DB database ID. Required.               |
| username       | MessageText   | Username for Cassandra (leave empty for Astra DB).                            |
| token          | SecretString  | Password for Cassandra or token for Astra DB. Required.                       |
| keyspace       | MessageText   | Keyspace in Cassandra or namespace in Astra DB. Required.                     |
| table_name     | MessageText   | Name of the table or collection for storing messages. Required.               |
| session_id     | MessageText   | Unique identifier for the chat session. Optional.                             |
| cluster_kwargs | Dictionary    | Additional keyword arguments for Cassandra cluster configuration. Optional.   |

### Outputs

| Name            | Type                    | Description                                                  |
|-----------------|-------------------------|--------------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of CassandraChatMessageHistory for the session.  |

## Mem0 Chat Memory

The Mem0 Chat Memory component retrieves and stores chat messages using Mem0 memory storage.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| mem0_config | Mem0 Configuration | Configuration dictionary for initializing Mem0 memory instance. |
| ingest_message | Message to Ingest | The message content to be ingested into Mem0 memory. |
| existing_memory | Existing Memory Instance | Optional existing Mem0 memory instance. |
| user_id | User ID | Identifier for the user associated with the messages. |
| search_query | Search Query | Input text for searching related memories in Mem0. |
| mem0_api_key | Mem0 API Key | API key for Mem0 platform (leave empty to use the local version). |
| metadata | Metadata | Additional metadata to associate with the ingested message. |
| openai_api_key | OpenAI API Key | API key for OpenAI. This item is required if you use OpenAI embeddings without a provided configuration. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| memory | Mem0 Memory | The resulting Mem0 Memory object after ingesting data. |
| search_results | Search Results | The search results from querying Mem0 memory. |


## Redis Chat Memory

This component retrieves and stores chat messages from Redis.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| host | hostname | IP address or hostname. |
| port | port | Redis Port Number. |
| database | database | Redis database. |
| username | Username | The Redis user name. |
| password | Password | The password for username. |
| key_prefix | Key prefix | Key prefix. |
| session_id | Session ID | Session ID for the message. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| memory | Memory | The Redis chat message history object |

## ZepChatMemory Component

This component creates a `ZepChatMessageHistory` instance, enabling storage and retrieval of chat messages using Zep, a memory server for Large Language Models (LLMs).

### Inputs

| Name          | Type          | Description                                               |
|---------------|---------------|-----------------------------------------------------------|
| url           | MessageText   | URL of the Zep instance. Required.                        |
| api_key       | SecretString  | API Key for authentication with the Zep instance.         |
| api_base_path | Dropdown      | API version to use. Options: "api/v1" or "api/v2".        |
| session_id    | MessageText   | Unique identifier for the chat session. Optional.         |

### Outputs

| Name            | Type                    | Description                                           |
|-----------------|-------------------------|-------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of ZepChatMessageHistory for the session. |