/**
 * Tests for the SSE streaming logic used by Agent chat.
 *
 * Covers: parseSSEEvent, processSSELine, postAgentChatStream.
 */

// Polyfill TextEncoder/TextDecoder for jsdom environment
import {
  TextDecoder as NodeTextDecoder,
  TextEncoder as NodeTextEncoder,
} from "util";
global.TextEncoder = NodeTextEncoder as unknown as typeof TextEncoder;
global.TextDecoder = NodeTextDecoder as unknown as typeof TextDecoder;

// ── Mocks ────────────────────────────────────────────────────────
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => (key === "AGENTS" ? "/api/v1/agents" : ""),
}));

// ── Imports ──────────────────────────────────────────────────────
import type { AgentSSEEvent } from "../types";
import { postAgentChatStream } from "../post-agent-chat-stream";

// ── Helpers ──────────────────────────────────────────────────────
function encode(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

function sseData(event: AgentSSEEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

function createMockReader(chunks: Uint8Array[]) {
  let index = 0;
  return {
    read: jest.fn(async () => {
      if (index < chunks.length) {
        return { done: false, value: chunks[index++] };
      }
      return { done: true, value: undefined };
    }),
    cancel: jest.fn().mockResolvedValue(undefined),
    releaseLock: jest.fn(),
  };
}

function createMockResponse(
  status: number,
  chunks: Uint8Array[],
  textBody?: string,
): Response {
  if (status < 200 || status >= 300) {
    return {
      ok: false,
      status,
      text: jest.fn().mockResolvedValue(textBody ?? ""),
      body: null,
    } as unknown as Response;
  }

  return {
    ok: true,
    status: 200,
    body: { getReader: () => createMockReader(chunks) },
  } as unknown as Response;
}

function createSSEResponse(...events: AgentSSEEvent[]): Response {
  const text = events.map((e) => sseData(e)).join("");
  return createMockResponse(200, [encode(text)]);
}

function createNullBodyResponse(): Response {
  return {
    ok: true,
    status: 200,
    body: null,
  } as unknown as Response;
}

// Mock fetch
const mockFetch = jest.fn<
  Promise<Response>,
  [RequestInfo | URL, RequestInit?]
>();
global.fetch = mockFetch as typeof global.fetch;

beforeEach(() => {
  mockFetch.mockReset();
});

// ── Tests ────────────────────────────────────────────────────────
describe("postAgentChatStream", () => {
  describe("Happy path", () => {
    it("invokes onToken for each token event", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse(
          { event: "token", chunk: "Hello" },
          { event: "token", chunk: " world" },
          { event: "complete", data: {} },
        ),
      );

      const onToken = jest.fn();
      const onComplete = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onToken, onComplete },
      );

      expect(onToken).toHaveBeenCalledTimes(2);
      expect(onToken).toHaveBeenCalledWith({
        event: "token",
        chunk: "Hello",
      });
      expect(onToken).toHaveBeenCalledWith({
        event: "token",
        chunk: " world",
      });
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it("invokes onComplete with event data", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse({
          event: "complete",
          data: { result: "done" },
        }),
      );

      const onComplete = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onComplete },
      );

      expect(onComplete).toHaveBeenCalledWith({
        event: "complete",
        data: { result: "done" },
      });
    });

    it("stops reading after complete event", async () => {
      // Put complete first, then a token that should never be reached
      const text =
        sseData({ event: "complete", data: {} }) +
        sseData({ event: "token", chunk: "unreachable" });
      mockFetch.mockResolvedValue(
        createMockResponse(200, [encode(text)]),
      );

      const onToken = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onToken },
      );

      expect(onToken).not.toHaveBeenCalled();
    });
  });

  describe("Error handling", () => {
    it("calls onError when response is not ok with JSON detail", async () => {
      mockFetch.mockResolvedValue(
        createMockResponse(
          500,
          [],
          JSON.stringify({ detail: "Server error" }),
        ),
      );

      const onError = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onError },
      );

      expect(onError).toHaveBeenCalledWith({
        event: "error",
        message: "Server error",
      });
    });

    it("calls onError with plain text when JSON parse fails", async () => {
      mockFetch.mockResolvedValue(
        createMockResponse(502, [], "Bad Gateway"),
      );

      const onError = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onError },
      );

      expect(onError).toHaveBeenCalledWith({
        event: "error",
        message: "Bad Gateway",
      });
    });

    it("calls onError when body is null", async () => {
      mockFetch.mockResolvedValue(createNullBodyResponse());

      const onError = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onError },
      );

      expect(onError).toHaveBeenCalledWith({
        event: "error",
        message: "No response body",
      });
    });

    it("invokes onError callback for SSE error events", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse({
          event: "error",
          message: "Model not found",
        }),
      );

      const onError = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onError },
      );

      expect(onError).toHaveBeenCalledWith({
        event: "error",
        message: "Model not found",
      });
    });

    it("invokes onCancelled callback for cancelled events", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse({
          event: "cancelled",
          message: "User cancelled",
        }),
      );

      const onCancelled = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onCancelled },
      );

      expect(onCancelled).toHaveBeenCalledWith({
        event: "cancelled",
        message: "User cancelled",
      });
    });

    it("calls onError with generic message for empty error body", async () => {
      mockFetch.mockResolvedValue(createMockResponse(500, [], ""));

      const onError = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onError },
      );

      expect(onError).toHaveBeenCalledWith({
        event: "error",
        message: "Request failed",
      });
    });
  });

  describe("URL construction", () => {
    it("includes all optional params in URL", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse({ event: "complete", data: {} }),
      );

      await postAgentChatStream(
        "agent-42",
        {
          input_value: "test",
          provider: "openai",
          model_name: "gpt-4",
          session_id: "sess-1",
        },
        {},
      );

      const url = mockFetch.mock.calls[0][0] as string;

      expect(url).toContain("/api/v1/agents/agent-42/chat/stream");
      expect(url).toContain("input_value=test");
      expect(url).toContain("provider=openai");
      expect(url).toContain("model_name=gpt-4");
      expect(url).toContain("session_id=sess-1");
    });

    it("omits optional params when not provided", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse({ event: "complete", data: {} }),
      );

      await postAgentChatStream("agent-1", { input_value: "hi" }, {});

      const url = mockFetch.mock.calls[0][0] as string;

      expect(url).not.toContain("provider=");
      expect(url).not.toContain("model_name=");
      expect(url).not.toContain("session_id=");
    });

    it("sends POST with correct headers", async () => {
      mockFetch.mockResolvedValue(
        createSSEResponse({ event: "complete", data: {} }),
      );

      await postAgentChatStream("agent-1", { input_value: "hi" }, {});

      const opts = mockFetch.mock.calls[0][1] as RequestInit;
      expect(opts.method).toBe("POST");
      expect(opts.headers).toEqual({ Accept: "text/event-stream" });
      expect(opts.credentials).toBe("include");
    });
  });

  describe("Adversarial", () => {
    it("ignores non-SSE lines gracefully", async () => {
      const raw = `: keepalive\n\n${sseData({ event: "complete", data: {} })}`;
      mockFetch.mockResolvedValue(
        createMockResponse(200, [encode(raw)]),
      );

      const onComplete = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onComplete },
      );

      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it("handles malformed JSON in SSE data gracefully", async () => {
      const raw = `data: not-json\n\n${sseData({ event: "complete", data: {} })}`;
      mockFetch.mockResolvedValue(
        createMockResponse(200, [encode(raw)]),
      );

      const onToken = jest.fn();
      const onComplete = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onToken, onComplete },
      );

      expect(onToken).not.toHaveBeenCalled();
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it("handles chunks split across read boundaries", async () => {
      const full = sseData({ event: "token", chunk: "hi" });
      const part1 = full.slice(0, 15);
      const part2 = full.slice(15);
      const complete = sseData({ event: "complete", data: {} });

      mockFetch.mockResolvedValue(
        createMockResponse(200, [
          encode(part1),
          encode(part2),
          encode(complete),
        ]),
      );

      const onToken = jest.fn();
      const onComplete = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onToken, onComplete },
      );

      expect(onToken).toHaveBeenCalledWith({
        event: "token",
        chunk: "hi",
      });
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it("handles response with message field instead of detail", async () => {
      mockFetch.mockResolvedValue(
        createMockResponse(
          400,
          [],
          JSON.stringify({ message: "Bad request" }),
        ),
      );

      const onError = jest.fn();

      await postAgentChatStream(
        "agent-1",
        { input_value: "Hi" },
        { onError },
      );

      expect(onError).toHaveBeenCalledWith({
        event: "error",
        message: "Bad request",
      });
    });
  });
});
