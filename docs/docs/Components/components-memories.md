# Memories

Chat memory components store and retrieve chat messages by `session_id`.

## AstraDBChatMemory Component

This component creates an `AstraDBChatMessageHistory` instance, which allows for storing and retrieving chat messages using Astra DB, a cloud-native database service.

### Parameters

#### Inputs

| Name             | Type          | Description                                                           |
|------------------|---------------|-----------------------------------------------------------------------|
| collection_name  | String        | Name of the Astra DB collection for storing messages. Required.       |
| token            | SecretString  | Authentication token for Astra DB access. Required.                   |
| api_endpoint     | SecretString  | API endpoint URL for the Astra DB service. Required.                  |
| namespace        | String        | Optional namespace within Astra DB for the collection.                |
| session_id       | MessageText   | Chat session ID. Uses current session ID if not provided.             |

#### Outputs

| Name            | Type                    | Description                                               |
|-----------------|-------------------------|-----------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of AstraDBChatMessageHistory for the session. |

## CassandraChatMemory Component

This component creates a `CassandraChatMessageHistory` instance, enabling storage and retrieval of chat messages using Apache Cassandra or DataStax Astra DB.

### Parameters

#### Inputs

| Name           | Type          | Description                                                                   |
|----------------|---------------|-------------------------------------------------------------------------------|
| database_ref   | MessageText   | Contact points for Cassandra or Astra DB database ID. Required.               |
| username       | MessageText   | Username for Cassandra (leave empty for Astra DB).                            |
| token          | SecretString  | Password for Cassandra or token for Astra DB. Required.                       |
| keyspace       | MessageText   | Keyspace in Cassandra or namespace in Astra DB. Required.                     |
| table_name     | MessageText   | Name of the table or collection for storing messages. Required.               |
| session_id     | MessageText   | Unique identifier for the chat session. Optional.                             |
| cluster_kwargs | Dictionary    | Additional keyword arguments for Cassandra cluster configuration. Optional.   |

#### Outputs

| Name            | Type                    | Description                                                  |
|-----------------|-------------------------|--------------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of CassandraChatMessageHistory for the session.  |

## ZepChatMemory Component

This component creates a `ZepChatMessageHistory` instance, enabling storage and retrieval of chat messages using Zep, a memory server for Large Language Models (LLMs).

### Parameters

#### Inputs

| Name          | Type          | Description                                               |
|---------------|---------------|-----------------------------------------------------------|
| url           | MessageText   | URL of the Zep instance. Required.                        |
| api_key       | SecretString  | API Key for authentication with the Zep instance.         |
| api_base_path | Dropdown      | API version to use. Options: "api/v1" or "api/v2".        |
| session_id    | MessageText   | Unique identifier for the chat session. Optional.         |

#### Outputs

| Name            | Type                    | Description                                           |
|-----------------|-------------------------|-------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of ZepChatMessageHistory for the session. |