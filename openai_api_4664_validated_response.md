# Response for Issue #4664: OpenAI-Like API Support

Hi @win4r,

Thank you for your interest in OpenAI-like API support for Langflow. This is indeed a valuable feature that would greatly enhance Langflow's integration capabilities.

## Current Status

**🚀 Active Development**: There's currently an **open pull request (#9069)** implementing OpenAI compatibility that adds `/responses` endpoint with OpenAI-style API support.

## Verified Implementation Details

Based on PR #9069, the OpenAI compatibility feature includes:

### 1. OpenAI-Compatible Endpoint
A new `/responses` endpoint that accepts OpenAI-style requests:

```python
from openai import OpenAI

langflow_client = OpenAI(
    base_url=f"{langflow_url}/api/v1",
    api_key=langflow_key
)

response = langflow_client.responses.create(
    model=flow_id,
    input=prompt
)

response_text = response.output_text
```

### 2. Advanced Features
- **Session Support**: Pass session ID via `previous_response_id`
- **Tool Call Results**: Include tool outputs with `include=["tool_call.results"]`
- **Global Variable Override**: Use HTTP headers like `X-LANGFLOW-GLOBAL-VAR-VARNAME`
- **Streaming Support**: Compatible with OpenAI streaming responses

### 3. API Structure
- **New Router**: `openai_responses_router` integrated into existing API structure
- **Compatible Schemas**: Full OpenAI-compatible request/response models
- **Error Handling**: OpenAI-style error responses

## Integration Benefits

Once merged, this will enable:
- **Chat UIs**: Integration with any OpenAI-compatible interface
- **Third-Party Services**: Services like ElevenLabs Custom LLM feature
- **Existing Codebases**: Drop-in replacement for OpenAI endpoints
- **Development Tools**: Use with any OpenAI-compatible tooling

## Related Issues (Verified)

- **Issue #7085** (CLOSED): "Add support for OpenAI's Responses API" - About using OpenAI's Responses API for faster tool calls, not providing OpenAI compatibility
- **Issue #7300** (OPEN): "Add support for OpenAI Compatible APIs" - About supporting custom model names in OpenAI component, different from this request

## Current Alternatives

While awaiting the PR merge:
1. Use Langflow's existing `/api/v1/run/{flow_id}` endpoint with custom wrapper
2. Implement your own adapter layer around Langflow's current APIs

## Timeline

The PR (#9069) is currently open and under review. Monitor it for:
- Implementation updates
- Review feedback
- Merge timeline

## Technical Considerations

As noted by @ogabrielluiz, the challenge is that "flows don't always return text data." PR #9069 appears to address this with proper schema handling and response formatting.

This feature will significantly expand Langflow's integration ecosystem. The active PR shows concrete progress toward making this available.

Would you like updates when PR #9069 is merged?

Best regards,  
Langflow Support