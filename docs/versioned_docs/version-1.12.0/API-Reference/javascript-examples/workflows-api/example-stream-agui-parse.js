const base = (process.env.LANGFLOW_URL ?? process.env.LANGFLOW_SERVER_URL ?? "").replace(/\/$/, "");
const flowId = process.env.FLOW_ID ?? "67ccd2be-17f0-8190-81ff-3bb2cf6508e6";
const apiKey = process.env.LANGFLOW_API_KEY ?? "";
const sessionId = process.env.AGUI_SESSION_ID ?? "thread-123";

const NUMBER = /-?\d+(?:\.\d+)?/;

function numbersFromToolResult(raw) {
  if (raw == null) {
    return [];
  }
  if (typeof raw === "number") {
    return [String(raw)];
  }
  if (typeof raw === "string") {
    return raw.match(new RegExp(NUMBER.source, "g")) ?? [];
  }
  if (typeof raw === "object") {
    for (const key of ["content", "result", "output", "text"]) {
      const value = raw[key];
      if (value == null) {
        continue;
      }
      if (typeof value === "number") {
        return [String(value)];
      }
      const asText = typeof value === "string" ? value : JSON.stringify(value);
      const matches = asText.match(new RegExp(NUMBER.source, "g"));
      if (matches?.length) {
        return matches;
      }
    }
    const serialized = JSON.stringify(raw);
    return serialized.match(new RegExp(NUMBER.source, "g")) ?? [];
  }
  return String(raw).match(new RegExp(NUMBER.source, "g")) ?? [];
}

function extractNumber(text, toolResults) {
  for (let i = toolResults.length - 1; i >= 0; i -= 1) {
    const matches = numbersFromToolResult(toolResults[i]);
    if (matches.length) {
      return Number(matches[matches.length - 1]);
    }
  }
  const matches = text.match(new RegExp(NUMBER.source, "g"));
  return matches?.length ? Number(matches[matches.length - 1]) : null;
}

async function ask(prompt) {
  let text = "";
  const toolResults = [];

  const response = await fetch(`${base}/api/v2/workflows`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      flow_id: flowId,
      input_value: prompt,
      mode: "stream",
      stream_protocol: "agui",
      session_id: sessionId,
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
      const event = JSON.parse(line.slice(5).trim());
      switch (event.type) {
        case "TEXT_MESSAGE_CONTENT":
          text += event.delta ?? "";
          break;
        case "TOOL_CALL_RESULT":
          toolResults.push(event.content ?? event.result);
          break;
        case "RUN_ERROR":
          throw new Error(event.message ?? "Run failed");
        case "RUN_FINISHED":
          await reader.cancel();
          return { text, toolResults };
        default:
          break;
      }
    }
  }

  return { text, toolResults };
}

async function main() {
  const prompt1 = process.env.AGUI_PROMPT1 ?? "What is 847 divided by 7?";
  const multiplier = Number(process.env.AGUI_MULTIPLIER ?? "3");

  console.log(`User: ${prompt1}`);
  const { text: reply1, toolResults: tools1 } = await ask(prompt1);
  const quotient = extractNumber(reply1, tools1);
  if (quotient == null) {
    throw new Error("Could not extract a number from run 1.");
  }
  console.log(`Assistant: ${reply1.trim()}`);
  console.log(`Extracted: ${quotient}`);

  const prompt2 = process.env.AGUI_PROMPT2 ?? `Now multiply ${quotient} by ${multiplier}.`;
  console.log(`\nUser: ${prompt2}`);
  const { text: reply2, toolResults: tools2 } = await ask(prompt2);
  const product = extractNumber(reply2, tools2);
  if (product == null) {
    throw new Error("Could not extract a number from run 2.");
  }
  console.log(`Assistant: ${reply2.trim()}`);

  console.log("\n=== Calculation chain ===");
  console.log(`847 ÷ 7 = ${quotient}`);
  console.log(`${quotient} × ${multiplier} = ${product}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
