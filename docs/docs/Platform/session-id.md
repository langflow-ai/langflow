---
title: Session ID
slug: /platform-session-id
---

Session ID is a unique identifier for client/server connections. A single session equals the duration of a client's connection to a server.

In the Langflow **Playground**, current sessions are listed on the left side of the pane.

Langflow uses session IDs to track different chat interactions within flows. This allows multiple chat sessions to exist in a single flow. Messages are stored in the database with session IDs as a reference.

This differentiation between users per session is helpful in managing client/server connections, but is also important in maintaining separate conversational contexts within a single flow. LLMs rely on past interactions to generate responses to queries, and if these conversations aren't separated, the responses becomes less useful, or even confused.

## Customize session ID

Custom session IDs can be set as part of the payload in API calls, or as advanced settings in individual components. The API session ID value takes precedence. If no session ID is specified, the flow ID is assigned.

If you set a custom session ID in a payload, all downstream components use the upstream component's session ID value.

```
curl -X POST "http://127.0.0.1:7860/api/v1/run/$FLOW_ID" \
-H 'Content-Type: application/json' \
-d '{
    "session_id": "my_custom_session_value",
    "input_value": "message",
    "input_type": "chat",
    "output_type": "chat"
}'
```

The `my_custom_session_value` value will be used in components that accept it, and the stored messages from this flow will be stored in `langflow.db` with their respective `session_id` values.

## Retrieval of messages from memory by session ID

The default memory component helper can access the default langflow.db sqlite database, or an external database if you've configured one. 

The component accepts `sessionID` as a filter parameter, and will use the session ID value from upstream automatically to retrieve message history by session ID from storage.

Messages can also be retrieved by `session_id` from the /monitor endpoint in the API.

For more information, see the [API examples](https://docs.langflow.org/api-reference-api-examples#get-messages).

