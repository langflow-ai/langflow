(async () => {
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
      input_value: "Tell me a short joke.",
      mode: "stream",
      session_id: "session-123",
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data:")) {
        continue;
      }
      const frame = JSON.parse(line.slice(5).trim());
      if (frame.event === "token") {
        process.stdout.write(frame.data.chunk);
      }
    }
  }

  buffer += decoder.decode();
  if (buffer.trim().startsWith("data:")) {
    const frame = JSON.parse(buffer.slice(5).trim());
    if (frame.event === "token") {
      process.stdout.write(frame.data.chunk);
    }
  }

  process.stdout.write("\n");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
