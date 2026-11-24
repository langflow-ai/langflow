(async () => {
  const base = (process.env.LANGFLOW_URL ?? process.env.LANGFLOW_SERVER_URL ?? "").replace(/\/$/, "");
  const flowId = process.env.FLOW_ID ?? "";
  const apiKey = process.env.LANGFLOW_API_KEY ?? "";

  const headers = {
    "Content-Type": "application/json",
    "x-api-key": apiKey,
  };

  const start = await fetch(`${base}/api/v2/workflows`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      flow_id: flowId,
      input_value: "Process this in the background",
      session_id: "session-456",
      mode: "background",
    }),
  });

  if (!start.ok) {
    throw new Error(`HTTP ${start.status}: ${await start.text()}`);
  }

  const { job_id: jobId } = await start.json();
  console.log(`Queued job ${jobId}`);

  while (true) {
    const status = await fetch(`${base}/api/v2/workflows?job_id=${encodeURIComponent(jobId)}`, {
      headers,
    });
    if (!status.ok) {
      throw new Error(`HTTP ${status.status}: ${await status.text()}`);
    }

    const body = await status.json();
    if (body.object === "response" && body.status === "completed") {
      console.log(body.output.text);
      break;
    }

    if (["failed", "cancelled", "timed_out"].includes(body.status)) {
      throw new Error(`Job ended with status ${body.status}`);
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
