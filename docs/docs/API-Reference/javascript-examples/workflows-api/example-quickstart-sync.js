const base = (process.env.LANGFLOW_URL ?? process.env.LANGFLOW_SERVER_URL ?? "").replace(/\/$/, "");
const flowId = process.env.FLOW_ID ?? "";
const apiKey = process.env.LANGFLOW_API_KEY ?? "";

const response = await fetch(`${base}/api/v2/workflows`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-api-key": apiKey,
  },
  body: JSON.stringify({
    flow_id: flowId,
    input_value: "what is 2+2",
    session_id: "session-123",
  }),
});

if (!response.ok) {
  throw new Error(`HTTP ${response.status}: ${await response.text()}`);
}

const body = await response.json();
console.log(body.output.text);
