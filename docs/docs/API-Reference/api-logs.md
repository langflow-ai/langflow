---
title: Logs endpoints
slug: /api-logs
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Retrieve logs for your Langflow flow.

This endpoint requires log retrieval to be enabled in your Langflow application.

To enable log retrieval, include these values in your `.env` file:

```text
LANGFLOW_ENABLE_LOG_RETRIEVAL=true
LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE=10000
LANGFLOW_LOG_LEVEL=DEBUG
```

For log retrieval to function, `LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE` needs to be greater than 0. The default value is `10000`.

Start Langflow with this `.env`:

```text
uv run langflow run --env-file .env
```

## Stream logs

Stream logs in real-time using Server-Sent Events (SSE).

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/logs-stream" \
  -H "accept: text/event-stream"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
keepalive

{"1736355791151": "2025-01-08T12:03:11.151218-0500 DEBUG Building Chat Input\n"}

{"1736355791485": "2025-01-08T12:03:11.485380-0500 DEBUG consumed event add_message-153bcd5d-ef4d-4ece-8cc0-47c6b6a9ef92 (time in queue, 0.0000, client 0.0001)\n"}

{"1736355791499": "2025-01-08T12:03:11.499704-0500 DEBUG consumed event end_vertex-3d7125cd-7b8a-44eb-9113-ed5b785e3cf3 (time in queue, 0.0056, client 0.0047)\n"}

{"1736355791502": "2025-01-08T12:03:11.502510-0500 DEBUG consumed event end-40d0b363-5618-4a23-bbae-487cd0b9594d (time in queue, 0.0001, client 0.0004)\n"}

{"1736355791513": "2025-01-08T12:03:11.513097-0500 DEBUG Logged vertex build: 729ff2f8-6b01-48c8-9ad0-3743c2af9e8a\n"}

{"1736355791834": "2025-01-08T12:03:11.834982-0500 DEBUG Telemetry data sent successfully.\n"}

{"1736355791941": "2025-01-08T12:03:11.941840-0500 DEBUG Telemetry data sent successfully.\n"}

keepalive
```

  </TabItem>
</Tabs>

## Retrieve logs with optional parameters

Retrieve logs with optional query parameters.

- `lines_before`: The number of logs before the timestamp or the last log.
- `lines_after`: The number of logs after the timestamp.
- `timestamp`: The timestamp to start getting logs from.

The default values for all three parameters is `0`.
With these values, the endpoint returns the last 10 lines of logs.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/logs?lines_before=0&lines_after=0&timestamp=0" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
{
  "1736354770500": "2025-01-08T11:46:10.500363-0500 DEBUG Creating starter project Document Q&A\n",
  "1736354770511": "2025-01-08T11:46:10.511146-0500 DEBUG Creating starter project Image Sentiment Analysis\n",
  "1736354770521": "2025-01-08T11:46:10.521018-0500 DEBUG Creating starter project SEO Keyword Generator\n",
  "1736354770532": "2025-01-08T11:46:10.532677-0500 DEBUG Creating starter project Sequential Tasks Agents\n",
  "1736354770544": "2025-01-08T11:46:10.544010-0500 DEBUG Creating starter project Custom Component Generator\n",
  "1736354770555": "2025-01-08T11:46:10.555513-0500 DEBUG Creating starter project Prompt Chaining\n",
  "1736354770588": "2025-01-08T11:46:10.588105-0500 DEBUG Create service ServiceType.CHAT_SERVICE\n",
  "1736354771021": "2025-01-08T11:46:11.021817-0500 DEBUG Telemetry data sent successfully.\n",
  "1736354775619": "2025-01-08T11:46:15.619545-0500 DEBUG Create service ServiceType.STORE_SERVICE\n",
  "1736354775699": "2025-01-08T11:46:15.699661-0500 DEBUG File 046-rocket.svg retrieved successfully from flow /Users/mendon.kissling/Library/Caches/langflow/profile_pictures/Space.\n"
}
```

  </TabItem>
</Tabs>