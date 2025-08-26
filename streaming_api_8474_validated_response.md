# Response for Issue #8474: No Output When Using stream=true

Hi @lahok,

Thank you for reporting this streaming API issue. I need to correct some misinformation: **The `/api/v1/run/{flow_id}?stream=true` endpoint is NOT deprecated** - it's actively maintained in the current codebase.

## Issue Analysis

The streaming endpoint exists at `/api/v1/run/{flow_id}` (implemented in `src/backend/base/langflow/api/v1/endpoints.py:273`) and accepts a `stream` query parameter. However, you're experiencing a known issue where it returns HTTP 200 but produces no output.

## Known Streaming Issues

Based on similar reports, streaming fails in specific scenarios:

1. **If-Else Components** - Issue #8103 confirms streaming doesn't work with conditional logic components
2. **Non-ChatOutput Targets** - Issue #7552 shows streaming fails when the target node isn't a ChatOutput component
3. **General Reliability** - Issue #8990 reports API not responding with `stream=true`

## Recommended Solutions

### Option 1: Use the Build API (Most Reliable)

The Build API provides better streaming reliability:

```bash
# Step 1: Start flow execution
curl -X POST \
  "http://localhost:7860/api/v1/build/$FLOW_ID/flow" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "inputs": {
      "input_value": "Your input here"
    }
  }'
```

Response:
```json
{"id": "job-uuid-here"}
```

```bash
# Step 2: Stream events
curl -X GET \
  "http://localhost:7860/api/v1/build/job-uuid-here/events?stream=true" \
  -H "x-api-key: $API_KEY"
```

### Option 2: Fix Your Flow Configuration

For the run API streaming to work:
1. Ensure your flow connects directly to a ChatOutput component
2. Remove If-Else components from the flow
3. Keep the flow structure simple (Input → LLM → ChatOutput)

### Option 3: Use Advanced Run API

Try the advanced endpoint which has better streaming support:

```bash
curl -X POST \
  "http://localhost:7860/api/v1/run/advanced/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "input_value": "Your input",
    "stream": true
  }'
```

## Working Example (Simplified Run with Stream)

If your flow meets the requirements, this should work:

```bash
curl -X POST \
  "http://localhost:7860/api/v1/run/$FLOW_ID?stream=true" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -H "Accept: text/event-stream" \
  -d '{
    "input_type": "chat",
    "input_value": "Hello"
  }'
```

Expected SSE response format:
```
event: token
data: {"token": "Hello"}

event: token
data: {"token": " there"}

event: end
data: {"result": {...}}
```

## Debugging Tips

1. **Test without streaming first**: Confirm `stream=false` works
2. **Check flow structure**: Streaming requires specific component arrangements
3. **Monitor server logs**: Look for streaming-related errors
4. **Use event listeners**: Some clients need special SSE handling

## Current Status

This is a known limitation affecting specific flow configurations. The endpoints are:
- `/api/v1/run/{flow_id}` - Simple run (streaming has limitations)
- `/api/v1/run/advanced/{flow_id}` - Advanced run (better streaming support)
- `/api/v1/build/{flow_id}/flow` + `/events` - Build API (most reliable for streaming)

The dosubot's claim about deprecation is incorrect - the endpoint exists and is tested in the current codebase. However, the Build API is recommended for production streaming use cases.

Let me know if you need help implementing any of these approaches or if you can share your flow structure for more specific guidance.

Best regards,
Langflow Support