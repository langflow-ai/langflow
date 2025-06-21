---
title: Monitor endpoints
slug: /api-monitor
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/monitor` endpoint to monitor and modify messages passed between Langflow components, vertex builds, and transactions.

## Get Vertex builds

Retrieve Vertex builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "vertex_builds": {
    "ChatInput-NCmix": [
      {
        "data": {
          "results": {
            "message": {
              "text_key": "text",
              "data": {
                "timestamp": "2024-12-23 19:10:57",
                "sender": "User",
                "sender_name": "User",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello",
                "files": [],
                "error": "False",
                "edit": "False",
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": "False",
                  "source": {
                    "id": "None",
                    "display_name": "None",
                    "source": "None"
                  },
                  "icon": "",
                  "allow_markdown": "False",
                  "positive_feedback": "None",
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "c95bed34-f906-4aa6-84e4-68553f6db772",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "default_value": "",
              "text": "Hello",
              "sender": "User",
              "sender_name": "User",
              "files": [],
              "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "timestamp": "2024-12-23 19:10:57+00:00",
              "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "error": "False",
              "edit": "False",
              "properties": {
                "text_color": "",
                "background_color": "",
                "edited": "False",
                "source": {
                  "id": "None",
                  "display_name": "None",
                  "source": "None"
                },
                "icon": "",
                "allow_markdown": "False",
                "positive_feedback": "None",
                "state": "complete",
                "targets": []
              },
              "category": "message",
              "content_blocks": []
            }
          },
          "outputs": {
            "message": {
              "message": {
                "timestamp": "2024-12-23T19:10:57",
                "sender": "User",
                "sender_name": "User",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello",
                "files": [],
                "error": false,
                "edit": false,
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": false,
                  "source": {
                    "id": null,
                    "display_name": null,
                    "source": null
                  },
                  "icon": "",
                  "allow_markdown": false,
                  "positive_feedback": null,
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "c95bed34-f906-4aa6-84e4-68553f6db772",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "type": "object"
            }
          },
          "logs": { "message": [] },
          "message": {
            "message": "Hello",
            "sender": "User",
            "sender_name": "User",
            "files": [],
            "type": "object"
          },
          "artifacts": {
            "message": "Hello",
            "sender": "User",
            "sender_name": "User",
            "files": [],
            "type": "object"
          },
          "timedelta": 0.015060124918818474,
          "duration": "15 ms",
          "used_frozen_result": false
        },
        "artifacts": {
          "message": "Hello",
          "sender": "User",
          "sender_name": "User",
          "files": [],
          "type": "object"
        },
        "params": "- Files: []\n  Message: Hello\n  Sender: User\n  Sender Name: User\n  Type: object\n",
        "valid": true,
        "build_id": "40aa200e-74db-4651-b698-f80301d2b26b",
        "id": "ChatInput-NCmix",
        "timestamp": "2024-12-23T19:10:58.772766Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ],
    "Prompt-BEn9c": [
      {
        "data": {
          "results": {},
          "outputs": {
            "prompt": {
              "message": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "type": "text"
            }
          },
          "logs": { "prompt": [] },
          "message": {
            "prompt": {
              "repr": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "raw": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "type": "text"
            }
          },
          "artifacts": {
            "prompt": {
              "repr": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "raw": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "type": "text"
            }
          },
          "timedelta": 0.0057758750626817346,
          "duration": "6 ms",
          "used_frozen_result": false
        },
        "artifacts": {
          "prompt": {
            "repr": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
            "raw": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
            "type": "text"
          }
        },
        "params": "None",
        "valid": true,
        "build_id": "39bbbfde-97fd-42a5-a9ed-d42a5c5d532b",
        "id": "Prompt-BEn9c",
        "timestamp": "2024-12-23T19:10:58.781019Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ],
    "OpenAIModel-7AjrN": [
      {
        "data": {
          "results": {},
          "outputs": {
            "text_output": {
              "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "type": "text"
            },
            "model_output": { "message": "", "type": "unknown" }
          },
          "logs": { "text_output": [] },
          "message": {
            "text_output": {
              "repr": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "raw": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "type": "text"
            }
          },
          "artifacts": {
            "text_output": {
              "repr": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "raw": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "type": "text"
            }
          },
          "timedelta": 1.034765167045407,
          "duration": "1.03 seconds",
          "used_frozen_result": false
        },
        "artifacts": {
          "text_output": {
            "repr": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "raw": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "type": "text"
          }
        },
        "params": "None",
        "valid": true,
        "build_id": "4f0ae730-a266-4d35-b89f-7b825c620a0f",
        "id": "OpenAIModel-7AjrN",
        "timestamp": "2024-12-23T19:10:58.790484Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ],
    "ChatOutput-sfUhT": [
      {
        "data": {
          "results": {
            "message": {
              "text_key": "text",
              "data": {
                "timestamp": "2024-12-23 19:10:58",
                "sender": "Machine",
                "sender_name": "AI",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
                "files": [],
                "error": "False",
                "edit": "False",
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": "False",
                  "source": {
                    "id": "OpenAIModel-7AjrN",
                    "display_name": "OpenAI",
                    "source": "gpt-4o-mini"
                  },
                  "icon": "OpenAI",
                  "allow_markdown": "False",
                  "positive_feedback": "None",
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "5688356d-9f30-40ca-9907-79a7a2fc16fd",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "default_value": "",
              "text": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "sender": "Machine",
              "sender_name": "AI",
              "files": [],
              "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "timestamp": "2024-12-23 19:10:58+00:00",
              "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "error": "False",
              "edit": "False",
              "properties": {
                "text_color": "",
                "background_color": "",
                "edited": "False",
                "source": {
                  "id": "OpenAIModel-7AjrN",
                  "display_name": "OpenAI",
                  "source": "gpt-4o-mini"
                },
                "icon": "OpenAI",
                "allow_markdown": "False",
                "positive_feedback": "None",
                "state": "complete",
                "targets": []
              },
              "category": "message",
              "content_blocks": []
            }
          },
          "outputs": {
            "message": {
              "message": {
                "timestamp": "2024-12-23T19:10:58",
                "sender": "Machine",
                "sender_name": "AI",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
                "files": [],
                "error": false,
                "edit": false,
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": false,
                  "source": {
                    "id": "OpenAIModel-7AjrN",
                    "display_name": "OpenAI",
                    "source": "gpt-4o-mini"
                  },
                  "icon": "OpenAI",
                  "allow_markdown": false,
                  "positive_feedback": null,
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "5688356d-9f30-40ca-9907-79a7a2fc16fd",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "type": "object"
            }
          },
          "logs": { "message": [] },
          "message": {
            "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "sender": "Machine",
            "sender_name": "AI",
            "files": [],
            "type": "object"
          },
          "artifacts": {
            "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "sender": "Machine",
            "sender_name": "AI",
            "files": [],
            "type": "object"
          },
          "timedelta": 0.017838125000707805,
          "duration": "18 ms",
          "used_frozen_result": false
        },
        "artifacts": {
          "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
          "sender": "Machine",
          "sender_name": "AI",
          "files": [],
          "type": "object"
        },
        "params": "- Files: []\n  Message: Hello! 🌟 I'm excited to help you get started on your journey to building\n    something fresh! What do you have in mind? Whether it's a project, an idea, or\n    a concept, let's dive in and make it happen!\n  Sender: Machine\n  Sender Name: AI\n  Type: object\n",
        "valid": true,
        "build_id": "1e8b908b-aba7-403b-9e9b-eca92bb78668",
        "id": "ChatOutput-sfUhT",
        "timestamp": "2024-12-23T19:10:58.813268Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ]
  }
}
```

  </TabItem>
</Tabs>

## Delete Vertex builds

Delete Vertex builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H "accept: */*"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
204 No Content
```

  </TabItem>
</Tabs>

## Get messages

Retrieve a list of all messages:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/messages" \
  -H "accept: application/json"
```

To filter messages, use the `flow_id`, `session_id`, `sender`, and `sender_name` query parameters.

To sort the results, use the `order_by` query parameter.

This example retrieves messages sent by `Machine` and `AI` in a given chat session (`session_id`) and orders the messages by timestamp.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/messages?flow_id=$FLOW_ID&session_id=01ce083d-748b-4b8d-97b6-33adbb6a528a&sender=Machine&sender_name=AI&order_by=timestamp" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "id": "1c1d6134-9b8b-4079-931c-84dcaddf19ba",
    "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
    "timestamp": "2024-12-23 19:20:11 UTC",
    "sender": "Machine",
    "sender_name": "AI",
    "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
    "text": "Hello! It's great to see you here! What exciting project or idea are you thinking about diving into today? Whether it's something fresh and innovative or a classic concept with a twist, I'm here to help you get started! Let's brainstorm together!",
    "files": "[]",
    "edit": false,
    "properties": {
      "text_color": "",
      "background_color": "",
      "edited": false,
      "source": {
        "id": "OpenAIModel-7AjrN",
        "display_name": "OpenAI",
        "source": "gpt-4o-mini"
      },
      "icon": "OpenAI",
      "allow_markdown": false,
      "positive_feedback": null,
      "state": "complete",
      "targets": []
    },
    "category": "message",
    "content_blocks": []
  }
]
```

  </TabItem>
</Tabs>

## Delete messages

Delete specific messages by their IDs.

This example deletes the message retrieved in the previous Get messages example.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -v -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/messages" \
  -H "accept: */*" \
  -H "Content-Type: application/json" \
  -d '["MESSAGE_ID_1", "MESSAGE_ID_2"]'
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
204 No Content
```

  </TabItem>
</Tabs>

## Update message

Update a specific message by its ID.

This example updates the `text` value of message `3ab66cc6-c048-48f8-ab07-570f5af7b160`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PUT \
  "$LANGFLOW_URL/api/v1/monitor/messages/3ab66cc6-c048-48f8-ab07-570f5af7b160" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "text": "testing 1234"
}'
```

</TabItem>
  <TabItem value="result" label="Result">

```json
{
  "timestamp": "2024-12-23T18:49:06",
  "sender": "string",
  "sender_name": "string",
  "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
  "text": "testing 1234",
  "files": ["string"],
  "error": true,
  "edit": true,
  "properties": {
    "text_color": "string",
    "background_color": "string",
    "edited": false,
    "source": { "id": "string", "display_name": "string", "source": "string" },
    "icon": "string",
    "allow_markdown": false,
    "positive_feedback": true,
    "state": "complete",
    "targets": []
  },
  "category": "message",
  "content_blocks": [],
  "id": "3ab66cc6-c048-48f8-ab07-570f5af7b160",
  "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
}
```

  </TabItem>
</Tabs>

## Update session ID

Update the session ID for messages.

This example updates the `session_ID` value `01ce083d-748b-4b8d-97b6-33adbb6a528a` to `different_session_id`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PATCH \
  "$LANGFLOW_URL/api/v1/monitor/messages/session/01ce083d-748b-4b8d-97b6-33adbb6a528a?new_session_id=different_session_id" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "id": "8dd7f064-e63a-4773-b472-ca0475249dfd",
    "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
    "timestamp": "2024-12-23 18:49:55 UTC",
    "sender": "User",
    "sender_name": "User",
    "session_id": "different_session_id",
    "text": "message",
    "files": "[]",
    "edit": false,
    "properties": {
      "text_color": "",
      "background_color": "",
      "edited": false,
      "source": {
        "id": null,
        "display_name": null,
        "source": null
      },
      "icon": "",
      "allow_markdown": false,
      "positive_feedback": null,
      "state": "complete",
      "targets": []
    },
    "category": "message",
    "content_blocks": []
  }
]
```

  </TabItem>
</Tabs>

## Delete messages by session

Delete all messages for a specific session.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/messages/session/different_session_id_2" \
  -H "accept: */*"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
HTTP/1.1 204 No Content
```

  </TabItem>
</Tabs>

## Get transactions

Retrieve all transactions (interactions between components) for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/transactions?flow_id=$FLOW_ID&page=1&size=50" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "items": [
    {
      "timestamp": "2024-12-23T20:05:01.061Z",
      "vertex_id": "string",
      "target_id": "string",
      "inputs": {},
      "outputs": {},
      "status": "string",
      "error": "string",
      "flow_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
  ],
  "total": 0,
  "page": 1,
  "size": 1,
  "pages": 0
}
```

  </TabItem>
</Tabs>

## See also

- [Session ID](/session-id)