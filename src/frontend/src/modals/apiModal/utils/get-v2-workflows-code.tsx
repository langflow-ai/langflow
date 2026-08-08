import { getBaseUrl } from "@/customization/utils/custom-code-samples";

/**
 * Code generators for the v2 (beta) API Access tab.
 *
 * These target `POST /api/v2/workflows` (the native `WorkflowRunRequest`
 * body, see `controllers/API/agui/run-agent.ts`), not the v1 `/run`
 * endpoint. Each generator returns a two-step block: a default run that
 * returns the whole result, and a streaming run.
 *
 * Notes baked into the snippets (from the v2 endpoint's behavior):
 * - `flow_id` must be a bare UUID; the endpoint rejects the `flow_...` form.
 * - `mode` defaults to a single response and `stream_protocol` defaults to
 *   `langflow`, so the minimal body is just `{flow_id, input_value}`.
 * - The default stream emits `data: {"event": "<type>", "data": {...}}`
 *   frames; consumers switch on the `event` field. The typed AG-UI protocol
 *   is opt-in via `"stream_protocol": "agui"`.
 * - Send `x-api-key` against a deployment (read from an env var, never
 *   inlined). A 403 there means a missing or wrong key, not a permission
 *   problem.
 */

const ENDPOINT = "/api/v2/workflows";

interface V2CodeOptions {
  flowId: string;
  inputValue: string;
  tweaks?: Record<string, unknown>;
  shouldDisplayApiKey: boolean;
}

type Step = { title: string; code: string; description?: string };

const SYNC_TITLE = "Get the full result";
const STREAM_TITLE = "Stream the result as it runs";

const SYNC_DESC =
  'The request waits for your flow to finish, then returns the whole answer as one JSON response. The text reply is in "output.text"; the full per-component results are under "outputs". Simplest option, and what you want for scripts, automations, and back-end calls. A 403 means a missing or wrong API key, not a permissions problem.';
const STREAM_DESC =
  'The answer arrives piece by piece while the flow runs, so you can show it live (like ChatGPT typing) instead of waiting for the end. You get a stream of JSON events, one per "data:" line. Read each event\'s "event" field: text arrives in "add_message" and "token" events, and the run closes with "end". For typed AG-UI events instead, add "stream_protocol": "agui".';

function buildBody(
  flowId: string,
  inputValue: string,
  tweaks: Record<string, unknown> | undefined,
  extra: Record<string, unknown>,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    flow_id: flowId,
    input_value: inputValue,
    ...extra,
  };
  if (tweaks && Object.keys(tweaks).length > 0) {
    body.tweaks = tweaks;
  }
  return body;
}

function toPythonLiteral(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 4)
    .replace(/": true/g, '": True')
    .replace(/": false/g, '": False')
    .replace(/": null/g, '": None');
}

/** cURL snippets for the v2 workflows endpoint (full result + streaming). */
export function getV2WorkflowsCurlCode({
  flowId,
  inputValue,
  tweaks,
  shouldDisplayApiKey,
}: V2CodeOptions): { steps: Step[] } {
  const url = `${getBaseUrl()}${ENDPOINT}`;

  const curl = (flags: string[], body: string): string => {
    const lines = [
      `curl ${flags.join(" ")} "${url}"`,
      `-H "Content-Type: application/json"`,
    ];
    if (shouldDisplayApiKey) lines.push(`-H "x-api-key: $LANGFLOW_API_KEY"`);
    lines.push(`-d '${body}'`);
    return lines.map((line, i) => (i === 0 ? line : `  ${line}`)).join(" \\\n");
  };

  const syncBody = JSON.stringify(
    buildBody(flowId, inputValue, tweaks, {}),
    null,
    2,
  );
  const streamBody = JSON.stringify(
    buildBody(flowId, inputValue, tweaks, { mode: "stream" }),
    null,
    2,
  );

  const syncPeek = `

# Returns one JSON object. The text reply is in "output.text":
# {
#   "flow_id": "${flowId}",
#   "session_id": "<pass this back to continue the same chat>",
#   "status": "completed",
#   "output": { "reason": "single", "text": "Hi there! How can I help?", "source": "ChatOutput-abc" },
#   "outputs": {
#     "ChatOutput-abc": { "type": "message", "display_name": "Chat Output", "content": "Hi there! How can I help?" }
#   }
# }
# (output.text is null when there is no single text answer; output.reason says why
#  ("multiple", "none", "non_string", "failed"), then read "outputs". A failed run still
#  returns HTTP 200, with status "failed" and a populated "errors" array.)`;

  const streamPeek = `

# Each line is one event. Read the "event" field to know what it carries:
# data: {"event": "add_message", "data": {...}}
# data: {"event": "token", "data": {"chunk": "Hi"}}
# data: {"event": "token", "data": {"chunk": " there!"}}
# data: {"event": "end", "data": {...}}`;

  return {
    steps: [
      {
        title: SYNC_TITLE,
        description: SYNC_DESC,
        code: curl(["-X", "POST"], syncBody) + syncPeek,
      },
      {
        title: STREAM_TITLE,
        description: STREAM_DESC,
        code: curl(["-N", "-X", "POST"], streamBody) + streamPeek,
      },
    ],
  };
}

/** Python (requests) snippets for the v2 workflows endpoint (full result + streaming). */
export function getV2WorkflowsPythonCode({
  flowId,
  inputValue,
  tweaks,
  shouldDisplayApiKey,
}: V2CodeOptions): { steps: Step[] } {
  const url = `${getBaseUrl()}${ENDPOINT}`;

  const headers = shouldDisplayApiKey
    ? `headers = {
    "Content-Type": "application/json",
    "x-api-key": os.environ["LANGFLOW_API_KEY"],
}`
    : `headers = {"Content-Type": "application/json"}`;

  const syncImports = shouldDisplayApiKey
    ? `import os\n\nimport requests`
    : `import requests`;
  const streamImports = shouldDisplayApiKey
    ? `import json\nimport os\n\nimport requests`
    : `import json\n\nimport requests`;

  const sync = `${syncImports}

url = "${url}"
payload = ${toPythonLiteral(buildBody(flowId, inputValue, tweaks, {}))}
${headers}

response = requests.post(url, json=payload, headers=headers)
response.raise_for_status()
result = response.json()

# The text reply is in output.text:
print(result["output"]["text"])`;

  const stream = `${streamImports}

url = "${url}"
payload = ${toPythonLiteral(buildBody(flowId, inputValue, tweaks, { mode: "stream" }))}
${headers}

# Events arrive as "data:" lines. Read each event's "event" field. When a
# component streams, the text arrives incrementally in "token" events; flows
# that don't stream deliver the full text in "add_message". The run ends with "end".
with requests.post(url, json=payload, headers=headers, stream=True) as response:
    response.raise_for_status()
    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if not decoded.startswith("data:"):
            continue
        event = json.loads(decoded[len("data:"):].strip())
        if event["event"] == "token":
            print(event["data"]["chunk"], end="", flush=True)
        elif event["event"] == "add_message":
            print(event["data"])
        elif event["event"] == "end":
            print("\\n[done]")`;

  return {
    steps: [
      { title: SYNC_TITLE, description: SYNC_DESC, code: sync },
      { title: STREAM_TITLE, description: STREAM_DESC, code: stream },
    ],
  };
}

/** JavaScript (fetch) snippets for the v2 workflows endpoint (full result + streaming). */
export function getV2WorkflowsJsCode({
  flowId,
  inputValue,
  tweaks,
  shouldDisplayApiKey,
}: V2CodeOptions): { steps: Step[] } {
  const url = `${getBaseUrl()}${ENDPOINT}`;

  const headers = shouldDisplayApiKey
    ? `{
    "Content-Type": "application/json",
    "x-api-key": process.env.LANGFLOW_API_KEY,
  }`
    : `{ "Content-Type": "application/json" }`;

  const sync = `const payload = ${JSON.stringify(buildBody(flowId, inputValue, tweaks, {}), null, 2)};

const response = await fetch("${url}", {
  method: "POST",
  headers: ${headers},
  body: JSON.stringify(payload),
});
const result = await response.json();

// The text reply is in output.text:
console.log(result.output.text);`;

  const stream = `const payload = ${JSON.stringify(buildBody(flowId, inputValue, tweaks, { mode: "stream" }), null, 2)};

// Events arrive as "data:" lines. Read each event's "event" field. When a
// component streams, text arrives incrementally in "token" events; flows that
// don't stream deliver the full text in "add_message". The run ends with "end".
const response = await fetch("${url}", {
  method: "POST",
  headers: ${headers},
  body: JSON.stringify(payload),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const frames = buffer.split("\\n\\n");
  buffer = frames.pop() ?? "";
  for (const frame of frames) {
    const dataLine = frame.split("\\n").find((line) => line.startsWith("data:"));
    if (!dataLine) continue;
    const event = JSON.parse(dataLine.slice(5).trim());
    if (event.event === "token") process.stdout.write(event.data.chunk);
    else if (event.event === "add_message") console.log(event.data);
    else if (event.event === "end") console.log("\\n[done]");
  }
}`;

  return {
    steps: [
      { title: SYNC_TITLE, description: SYNC_DESC, code: sync },
      { title: STREAM_TITLE, description: STREAM_DESC, code: stream },
    ],
  };
}
