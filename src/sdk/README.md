# Langflow Python SDK

## V2 workflows and server background jobs

These methods target the full Langflow 1.14 backend Workflow API, which is GA
as of 1.14. They do not provide durable background execution on bare `lfx serve`.
Use an API key and the UUID of an existing flow. Older server deployments may
require enabling `LANGFLOW_DEVELOPER_API_ENABLED`; the SDK propagates the server's
actual refusal rather than checking that setting locally.

### Synchronous result

```python
import os
from langflow_sdk import Client, WorkflowExecutionResponse, WorkflowRunRequest

with Client(os.environ["LANGFLOW_SERVER_URL"], api_key=os.environ["LANGFLOW_API_KEY"], timeout=120) as client:
    result = client.run_workflow(WorkflowRunRequest(
        flow_id=os.environ["FLOW_ID"], input_value="Hello"
    ))  # mode defaults to sync
    if isinstance(result, WorkflowExecutionResponse):
        print(result.output.reason, result.output.text)
```

`output.text` can be an empty string or null. Read `output.reason` and the full
`outputs` map rather than treating a falsey answer as a failed request. Response
extras and unknown status/reason strings are preserved. Timestamps, links and
`has_errors` are server values, not generated or inferred by the SDK.

### Submit, close the client, retrieve later

```python
import asyncio
import os
import time
from langflow_sdk import AsyncClient, WorkflowExecutionResponse, WorkflowJobResponse, WorkflowRunRequest

async def main():
    url, key = os.environ["LANGFLOW_SERVER_URL"], os.environ["LANGFLOW_API_KEY"]
    async with AsyncClient(url, api_key=key) as client:
        job = await client.run_workflow(WorkflowRunRequest(
            flow_id=os.environ["FLOW_ID"], mode="background", input_value="Hello"
        ))
        if not isinstance(job, WorkflowJobResponse):
            raise RuntimeError("Expected a server job acknowledgement")
        job_id = job.job_id  # store this ID for a later client/process

    deadline = time.monotonic() + 60
    async with AsyncClient(url, api_key=key) as client:
        while time.monotonic() < deadline:
            result = await client.get_workflow(job_id)
            if isinstance(result, WorkflowExecutionResponse):
                print(result.status, result.output.text)
                return
            if result.status not in {"queued", "in_progress"}:
                print("Stopped polling:", result.status)  # includes suspended/cancelled/future states
                return
            await asyncio.sleep(1)
        raise TimeoutError("Caller stopped polling; the server job may still be running")

asyncio.run(main())
```

Both clients expose `run_workflow`, `get_workflow` and `stop_workflow`. There is
no built-in polling, retry, key generation or automatic cancellation. The
existing V1 `run`, `run_flow`, `stream` and local asyncio `run_background` APIs
are unchanged. A local `BackgroundJob` is not a server workflow job.

### Stop acknowledgement and human input

`client.stop_workflow(job_id)` (or `await client.stop_workflow(job_id)`) returns
`WorkflowStopResponse` containing only `job_id` and optional `message`. There is
no machine-readable outcome/status. Do not parse the message to infer one; use
`get_workflow` for a subsequent snapshot. Acknowledgement does not prove active
work was interrupted, undo side effects, or guarantee cancellation across all
server backends. Completed background jobs keep their terminal state. Stopping
a sync job returns HTTP 409 `JOB_NOT_CANCELLABLE`.

A suspended status GET returns a job object, without a human-input prompt. This
SDK surface does not retrieve events, resume Human Input, or call public workflow
endpoints. Do not resubmit a paused flow as a substitute for the backend resume
API. Use the backend's documented background events/resume API separately. Sync
Human Input execution is not supported by this SDK's examples or safety claims.

### Request fields

`WorkflowRunRequest` forbids unknown fields and accepts only JSON modes `sync`
and `background`. Invalid mode is rejected before HTTP, even if the model was
mutated after construction. Other field combinations and permissions are
validated by the server. Optional `None` values are omitted on the wire; empty
strings/collections and `False` remain.

| Field | Sync | Background |
| --- | --- | --- |
| `flow_id`, `input_value`, `session_id`, `tweaks` | Existing flow UUID, chat input, session, server-authorized overrides | Persisted for the job |
| `globals` | Request-level string variables | Nonempty value rejected with 422 |
| `output_ids` | Select primary answer; full outputs still returned | Nonempty value rejected with 422 |
| `data` | Non-null value rejected with 422 | Live-canvas override, subject to server policy |
| `files` | Nonempty value rejected with 422 | Pre-uploaded paths, not an upload method |
| `start_component_id`, `stop_component_id` | Non-null value rejected with 422 | Partial-run boundaries |
| `stream_protocol` | Registry-validated; valid adapter has no sync streaming effect | Adapter for stored events, even though this SDK does not consume events |
| `expose_graph_state` | No streaming effect | Stored event scope; None leaves protocol default |
| `idempotency_key` | No deduplication effect | Optional owner-scoped key, maximum 255 characters |

Unknown `stream_protocol` returns 422 `UNKNOWN_STREAM_PROTOCOL` in both modes,
including an `available` adapter list. The default is `langflow`; `agui` is
another built-in adapter. Adapter names are not frozen into a client enum.
Legacy `X-LANGFLOW-GLOBAL-VAR-*` headers are rejected by the 1.14 V2 backend;
use body `globals` in sync mode. Earlier published web documentation may describe
older behavior for these fields.

A background idempotency key can reuse the same owner's queued, in-progress,
suspended or completed job. It is not a content fingerprint and is not scoped to
a flow: never reuse a key for different intended work. Failed, cancelled or
timed-out jobs permit a new run with that key. A deduplicated submit is a
queued-shaped acknowledgement, not a current status snapshot. A residual race
can return 409 `DUPLICATE_REQUEST`; the SDK does not retry automatically.

### Errors and timeouts

Failed background status GET raises `LangflowHTTPError` with status 500 and
structured detail code `JOB_FAILED`, including a possibly null `error_detail`.
A server compute timeout raises the same exception class with status 408 and
code `EXECUTION_TIMEOUT`, not a successful `status="timed_out"` result model.
The `detail` attribute preserves JSON objects, arrays, scalar values and null:

```python
from langflow_sdk import Client, LangflowHTTPError

def fetch_result(url, api_key, job_id):
    with Client(url, api_key=api_key) as client:
        try:
            return client.get_workflow(job_id)
        except LangflowHTTPError as exc:
            if isinstance(exc.detail, dict):
                print(exc.status_code, exc.detail.get("code"), exc.detail.get("error_detail"))
            else:
                print(exc.status_code, exc.detail)
            raise
```

Auth (401/403), not-found (404), and validation (422) retain the existing SDK
exception subclasses. An HTTPX network read timeout remains `httpx.ReadTimeout`;
it is distinct from a server HTTP 408 and the existing local V1
`LangflowTimeoutError`. Configure the client's HTTP timeout for the expected
sync duration. The server's `workflow_execution_timeout` limits attached runs;
`background_job_timeout` controls background compute (unlimited by default).
The SDK does not set those settings or promise survival across server restarts.

API references: [Workflow API](https://docs.langflow.org/workflow-api) and
[quickstart](https://docs.langflow.org/workflow-api-quickstart). The checked-in
1.14 server contract takes precedence over older published examples.
