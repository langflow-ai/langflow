const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v2/workflows`;

const options = {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
    flow_id: "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
    input_value: "Hello from a Langflow stream client",
    mode: "stream",
    session_id: "session-123",
  }),
};

const response = await fetch(url, options);
if (!response.ok) {
  throw new Error(`HTTP ${response.status}`);
}

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) {
    break;
  }
  process.stdout.write(decoder.decode(value));
}
