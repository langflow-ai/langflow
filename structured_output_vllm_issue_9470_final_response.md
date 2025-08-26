# Structured Output VLLM Issue #9470 - Final Response

Hi @Arron-Clague,

Thank you for reporting this issue with the Structured Output component and VLLM.

## Root Cause

The error `Completions.create() got an unexpected keyword argument ''` indicates that the `trustcall` library used by the Structured Output component is passing a malformed parameter that VLLM's OpenAI-compatible API doesn't recognize. This is a compatibility issue between the `trustcall` library and VLLM.

## Solution: Use OpenAI Component with JSON Mode

Since your CURL test shows VLLM works perfectly with the `response_format` parameter, you can achieve structured output using the **OpenAI component directly**:

### Configuration Steps:

1. **Use the OpenAI component** (not the Structured Output component)
2. Configure it as follows:
   - **Model Name**: `koni` (your custom model)
   - **OpenAI API Base**: `http://10.0.0.205:8999/v1`
   - **API Key**: Any dummy value (VLLM usually doesn't validate this)
   - **JSON Mode**: Enable this in Advanced settings
   - **Temperature**: 0 (for consistent outputs)

3. In your prompt, explicitly ask for JSON output with the structure you need:
   ```
   System: You are a helpful assistant that always responds in valid JSON format.
   User: Give me a JSON with keys name and age.
   ```

### Why This Works

- When JSON mode is enabled, the OpenAI component uses `response_format={"type": "json_object"}` which is exactly what your successful CURL command uses
- This avoids the `trustcall` library entirely, eliminating the compatibility issue
- You get the same structured output functionality without the problematic middleware

## Alternative: Prompt Component with OpenAI

You can also use a Prompt component connected to the OpenAI component:
1. Create a Prompt that instructs the model to output JSON
2. Connect it to the OpenAI component (configured as above with JSON mode enabled)
3. Parse the JSON response in your flow as needed

The OpenAI component with JSON mode will send the same `response_format` parameter that works in your CURL test.

Please try this approach and let me know if you encounter any issues!

Best regards,
Langflow Support Team