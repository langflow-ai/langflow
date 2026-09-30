#!/usr/bin/env node

import { createServer } from "node:http";

const host = process.env.LANGFLOW_TEST_OPENAI_HOST ?? "127.0.0.1";
const port = Number(process.env.LANGFLOW_TEST_OPENAI_PORT ?? "8787");
const model = "gpt-4o-mini";

function writeJson(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function flattenContent(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => (typeof part === "string" ? part : (part?.text ?? "")))
    .join(" ");
}

function latestPrompt(body) {
  return (
    (body.messages ?? [])
      .map((message) => flattenContent(message.content))
      .filter(Boolean)
      .at(-1) ?? ""
  );
}

function conversationText(body) {
  return (body.messages ?? [])
    .map((message) => flattenContent(message.content))
    .filter(Boolean)
    .join("\n");
}

function previouslyCalledTools(body) {
  return new Set(
    (body.messages ?? []).flatMap((message) =>
      message.role === "assistant" && Array.isArray(message.tool_calls)
        ? message.tool_calls
            .map((toolCall) => toolCall?.function?.name)
            .filter(Boolean)
        : [],
    ),
  );
}

function youtubeToolArguments(tool, conversation) {
  const properties = tool?.function?.parameters?.properties ?? {};
  const parameter = Object.hasOwn(properties, "video_url")
    ? "video_url"
    : Object.hasOwn(properties, "url")
      ? "url"
      : null;
  if (!parameter) return null;
  const videoUrl =
    conversation.match(
      /https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be)\/[^\s"'<>]+/i,
    )?.[0] ?? "https://www.youtube.com/watch?v=langflow-loopback";
  return JSON.stringify({ [parameter]: videoUrl });
}

function hasImageContent(body) {
  return (body.messages ?? []).some((message) =>
    Array.isArray(message.content)
      ? message.content.some(
          (part) =>
            part?.type === "image_url" ||
            part?.type === "input_image" ||
            part?.type === "image" ||
            Boolean(part?.image_url),
        )
      : false,
  );
}

function deterministicText(body) {
  const originalPrompt = latestPrompt(body);
  const prompt = originalPrompt.toLowerCase();
  const conversation = conversationText(body);
  if (hasImageContent(body)) {
    return (
      "Loopback image received: the attached chain.png is a chain-style Langflow diagram. " +
      "This distinctive response proves that the image content reached the OpenAI-compatible " +
      "model request instead of merely appearing as a filename in the playground."
    );
  }
  if (
    conversation.includes("LOOPBACK_YOUTUBE_COMMENTS_USED") &&
    conversation.includes("LOOPBACK_YOUTUBE_TRANSCRIPT_USED")
  ) {
    return (
      "LOOPBACK_YOUTUBE_COMMENTS_USED. LOOPBACK_YOUTUBE_TRANSCRIPT_USED. Content Summary: deterministic Langflow video fixture. Audience Reception: positive and engaged. " +
      "Synthesis: the transcript and comments consistently describe the workflow. " +
      "Recommendations: keep the explanation concise and include a practical demonstration."
    );
  }
  if (conversation.toLowerCase().includes("sentiment")) {
    const answer = conversation.includes("LOOPBACK_YOUTUBE_COMMENTS_USED")
      ? "LOOPBACK_YOUTUBE_COMMENTS_USED: positive"
      : "positive";
    return body.response_format || prompt.includes("json")
      ? JSON.stringify({ answer, sentiment: "positive" })
      : answer;
  }
  if (body.response_format || prompt.includes("json")) {
    return JSON.stringify({ answer: "deterministic loopback response" });
  }
  if (prompt.includes("hello, world")) {
    return '```python\nprint("Hello, World!")\n```';
  }
  if (prompt.includes("pirate")) {
    return "Ahoy matey! Hello from Langflow's deterministic loopback model.";
  }
  if (
    prompt.includes("what is my name") &&
    conversation.toLowerCase().includes("john doe")
  ) {
    return "Your name is John Doe. The loopback model recovered it from this session's conversation history.";
  }
  if (
    prompt.includes("what color is my car") &&
    conversation.toLowerCase().includes("my car is blue") &&
    conversation.toLowerCase().includes("pizza")
  ) {
    return "Your car is blue and you like to eat pizza. The loopback model recovered both details from this session's conversation history.";
  }
  if (
    prompt.includes("custom component") &&
    prompt.includes("langflow random number")
  ) {
    return `Here is a deterministic Langflow custom component:\n\n\`\`\`python\nfrom random import randint\nfrom lfx.custom import Component\nfrom lfx.io import Output\n\nclass LangflowRandomNumber(Component):\n    display_name = "Langflow Random Number"\n    outputs = [Output(name="number", display_name="Number", method="generate")]\n\n    def generate(self) -> int:\n        return randint(1, 100)\n\`\`\`\n\nThe component exposes a stable Number output while exercising Langflow's code rendering path.`;
  }
  if (conversation.includes("LOOPBACK_WEB_SEARCH_USED")) {
    return (
      `LOOPBACK_WEB_SEARCH_USED. Travel and social research completed from the checked-in tool fixture. ${originalPrompt} ` +
      "Day 1 includes local attractions, transit, and food; the requested cities and cuisine remain in the grounded plan."
    );
  }
  if (prompt.includes("travel plan")) {
    return `Travel plan — Day 1: ${originalPrompt}. Day 2: continue the trip with local food and cultural activities. This deterministic itinerary preserves the requested origin, destination, and cuisine so Langflow can verify the complete multi-agent workflow without a hosted provider.`;
  }
  return (
    "This is a deterministic response from Langflow's local OpenAI-compatible test server. " +
    "It keeps CI work repeatable while exercising the real Langflow graph, persistence, " +
    "streaming, tracing, usage, and message paths. The fixture deliberately returns enough " +
    "content for starter-project output assertions without relying on wording from a hosted " +
    "model. Langflow can therefore validate how each workflow transforms and displays this " +
    "response while every run receives the same stable input and output."
  );
}

function requestedToolCall(body) {
  const prompt = latestPrompt(body);
  const conversation = conversationText(body);
  const calledTools = previouslyCalledTools(body);
  const match = prompt.match(/CALL_TOOL:\s*([\w.-]+)(?:\s+(\{.*\}))?/i);
  if (!Array.isArray(body.tools)) return null;
  const arithmeticExpression = prompt
    .trim()
    .match(/^([\d\s()+\-*/.]+)\??$/)?.[1]
    ?.trim();
  const calculatorRequest = arithmeticExpression
    ? body.tools.find(
        (tool) =>
          /(?:calculat|evaluate_expression)/i.test(
            tool?.function?.name ?? "",
          ) && !calledTools.has(tool.function.name),
      )
    : null;
  const searchRequest = conversation.match(
    /(?:search first|web search|using google search|travel plan)/i,
  )
    ? body.tools.find(
        (tool) =>
          /(?:search|perform_search)/i.test(tool?.function?.name ?? "") &&
          !calledTools.has(tool.function.name),
      )
    : null;
  const youtubeContext = /(?:youtube(?:\.com| analysis)|youtu\.be)/i.test(
    conversation,
  );
  const youtubeCandidates = youtubeContext
    ? [
        body.tools.find((tool) => /comment/i.test(tool?.function?.name ?? "")),
        body.tools.find((tool) =>
          /transcript/i.test(tool?.function?.name ?? ""),
        ),
      ]
    : [];
  const youtubeRequest = youtubeCandidates.find(
    (tool) =>
      tool &&
      !calledTools.has(tool.function.name) &&
      youtubeToolArguments(tool, conversation),
  );
  const explicitRequest = match
    ? body.tools.find(
        (tool) =>
          tool?.function?.name === match[1] &&
          !calledTools.has(tool.function.name),
      )
    : null;
  const requested =
    explicitRequest ?? calculatorRequest ?? searchRequest ?? youtubeRequest;
  if (!requested) return null;
  const youtubeArguments =
    requested === youtubeRequest
      ? youtubeToolArguments(requested, conversation)
      : null;
  return {
    id: `call_loopback_${calledTools.size + 1}`,
    type: "function",
    function: {
      name: requested.function.name,
      arguments:
        match?.[2] ??
        (calculatorRequest
          ? JSON.stringify({ expression: arithmeticExpression })
          : youtubeArguments
            ? youtubeArguments
            : JSON.stringify({ query: prompt })),
    },
  };
}

function usage() {
  return { prompt_tokens: 11, completion_tokens: 13, total_tokens: 24 };
}

function chatCompletion(body) {
  const toolCall = requestedToolCall(body);
  return {
    id: "chatcmpl-loopback",
    object: "chat.completion",
    created: 1_700_000_000,
    model,
    choices: [
      {
        index: 0,
        finish_reason: toolCall ? "tool_calls" : "stop",
        message: {
          role: "assistant",
          content: toolCall ? null : deterministicText(body),
          ...(toolCall ? { tool_calls: [toolCall] } : {}),
        },
      },
    ],
    usage: usage(),
  };
}

function writeChatStream(response, body) {
  response.writeHead(200, {
    "cache-control": "no-cache",
    connection: "keep-alive",
    "content-type": "text/event-stream",
  });
  const toolCall = requestedToolCall(body);
  const chunks = toolCall
    ? [
        {
          choices: [
            {
              index: 0,
              delta: {
                role: "assistant",
                tool_calls: [{ index: 0, ...toolCall }],
              },
              finish_reason: null,
            },
          ],
        },
      ]
    : deterministicText(body)
        .split(/(?<=\s)/)
        .map((content) => ({
          choices: [
            {
              index: 0,
              delta: { role: "assistant", content },
              finish_reason: null,
            },
          ],
        }));

  for (const chunk of chunks) {
    response.write(
      `data: ${JSON.stringify({
        id: "chatcmpl-loopback",
        object: "chat.completion.chunk",
        created: 1_700_000_000,
        model,
        ...chunk,
      })}\n\n`,
    );
  }
  response.write(
    `data: ${JSON.stringify({
      id: "chatcmpl-loopback",
      object: "chat.completion.chunk",
      created: 1_700_000_000,
      model,
      choices: [
        {
          index: 0,
          delta: {},
          finish_reason: toolCall ? "tool_calls" : "stop",
        },
      ],
      usage: usage(),
    })}\n\n`,
  );
  response.end("data: [DONE]\n\n");
}

function responseApiBody(body) {
  const text = deterministicText({ messages: [{ content: body.input ?? "" }] });
  return {
    id: "resp_loopback",
    object: "response",
    created_at: 1_700_000_000,
    status: "completed",
    model,
    output: [
      {
        id: "msg_loopback",
        type: "message",
        role: "assistant",
        status: "completed",
        content: [{ type: "output_text", text, annotations: [] }],
      },
    ],
    output_text: text,
    usage: { input_tokens: 11, output_tokens: 13, total_tokens: 24 },
  };
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${host}:${port}`);

  if (request.method === "GET" && url.pathname === "/health") {
    writeJson(response, 200, { status: "ok" });
    return;
  }

  if (request.method === "GET" && url.pathname === "/v1/models") {
    writeJson(response, 200, {
      object: "list",
      data: [
        {
          id: model,
          object: "model",
          created: 1_700_000_000,
          owned_by: "langflow-tests",
        },
      ],
    });
    return;
  }

  try {
    if (request.method === "POST" && url.pathname === "/v1/chat/completions") {
      const body = await readJson(request);
      if (body.stream) writeChatStream(response, body);
      else writeJson(response, 200, chatCompletion(body));
      return;
    }

    if (request.method === "POST" && url.pathname === "/v1/embeddings") {
      const body = await readJson(request);
      const inputs = Array.isArray(body.input) ? body.input : [body.input];
      writeJson(response, 200, {
        object: "list",
        model: body.model ?? "text-embedding-3-small",
        data: inputs.map((_, index) => ({
          object: "embedding",
          index,
          embedding: Array.from({ length: 16 }, (_value, offset) =>
            Number(((index + offset + 1) / 100).toFixed(2)),
          ),
        })),
        usage: { prompt_tokens: inputs.length, total_tokens: inputs.length },
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/v1/responses") {
      const body = await readJson(request);
      const result = responseApiBody(body);
      if (!body.stream) {
        writeJson(response, 200, result);
        return;
      }
      response.writeHead(200, { "content-type": "text/event-stream" });
      response.write(
        `event: response.completed\ndata: ${JSON.stringify({ response: result })}\n\n`,
      );
      response.end("data: [DONE]\n\n");
      return;
    }
  } catch (error) {
    // The streaming branches above write headers before they finish, so a late
    // failure cannot be reported as JSON — calling writeHead twice throws
    // ERR_HTTP_HEADERS_SENT inside this async handler, and the resulting
    // unhandled rejection would tear down the fixture for the rest of the run.
    if (response.headersSent) {
      response.destroy();
    } else {
      writeJson(response, 400, { error: { message: String(error) } });
    }
    return;
  }

  writeJson(response, 404, {
    error: { message: `Unhandled test endpoint: ${url.pathname}` },
  });
});

server.listen(port, host, () => {
  process.stdout.write(
    `Loopback OpenAI fixture listening on http://${host}:${port}\n`,
  );
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => server.close(() => process.exit(0)));
}
