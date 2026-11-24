# API Examples (Local Test Harness)

Run all API example suites against a local Langflow server:

```bash
make api_examples_local
```

Run one test suite:

```bash
make api_examples_local suites=python
make api_examples_local suites=javascript
make api_examples_local suites=curl
```

The following examples are not executed in this harness:

- `api-build/build-flow-and-stream-events-2.py`
- `api-build/build-flow-and-stream-events-3.py`
- `api-flows-run/stream-llm-token-responses.py`
- `api-openai-responses/example-streaming-request.py`
- `api-logs/stream-logs.py`
- `api-logs/retrieve-logs-with-optional-parameters.py`
- `api-users/reset-password.py`