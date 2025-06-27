---
title: Use session ID to manage communication between components
slug: /session-id
---

Session ID is a unique identifier for client/server connections. A single session equals the duration of a client's connection to a server.

In the Langflow **Playground**, current sessions are listed on the left side of the pane.

Langflow uses session IDs to track different chat interactions within flows. This allows multiple chat sessions to exist in a single flow. Messages are stored in the database with session IDs as a reference.

This differentiation between users per session is helpful in managing client/server connections, but is also important in maintaining separate conversational contexts within a single flow. LLMs rely on past interactions to generate responses to queries, and if these conversations aren't separated, the responses becomes less useful, or even confused.

## Customize session ID

Custom session IDs can be set as part of the payload in API calls, or as advanced settings in individual components. The API session ID value takes precedence. If no session ID is specified, the flow ID is assigned.

If you set a custom session ID in a payload, all downstream components use the upstream component's session ID value.

```
curl --request POST \
  --url 'http://localhost:7860/api/v1/run/$FLOW_ID' \
  --header 'Content-Type: application/json' \
  --header 'x-api-key: LANGFLOW_API_KEY' \
  --data '{
  "input_value": "Hello",
  "output_type": "chat",
  "input_type": "chat",
  "session_id": "my_custom_session_value"
}'
```

The `my_custom_session_value` value is used in components that accept it, and the stored messages from this flow are stored in `langflow.db` with their respective `session_id` values.

## Retrieval of messages from memory by session ID

To retrieve messages from local Langflow memory, add a [Message history](/components-helpers#message-history) component to your flow.
The component accepts `sessionID` as a filter parameter, and uses the session ID value from upstream automatically to retrieve message history by session ID from storage.

Messages can be retrieved by `session_id` from the Langflow API at `GET /v1/monitor/messages`. For more information, see [Monitor endpoints](https://docs.langflow.org/api-monitor).

For an example of session ID in action, see [Use Session IDs in Langflow](https://www.youtube.com/watch?v=nJiF_eF21MY).