/**
 * Tests for SSE streaming (postAssistStream).
 *
 * Tests fetch setup, event dispatch, buffer reassembly, error handling,
 * and documents real bugs with it.failing().
 */

// Polyfill TextEncoder/TextDecoder for jsdom environment
import {
  TextDecoder as NodeTextDecoder,
  TextEncoder as NodeTextEncoder,
} from "util";
global.TextEncoder = NodeTextEncoder as unknown as typeof TextEncoder;
global.TextDecoder = NodeTextDecoder as unknown as typeof TextDecoder;

import type {
  AgenticCancelledEvent,
  AgenticCompleteEvent,
  AgenticErrorEvent,
  AgenticProgressEvent,
  AgenticSSEEvent,
  AgenticTokenEvent,
} from "../types";

// Mock getURL before importing the module under test
jest.mock("../../../helpers/constants", () => ({
  getURL: jest.fn(() => "http://localhost/api/v1/agentic/assist/stream"),
}));

import { postAssistStream } from "../use-post-assist-stream";

// Helper: encode a string as Uint8Array
function encode(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

// Helper: create SSE data line
function sseData(event: AgenticSSEEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

// Helper: create a mock reader that yields chunks then signals done
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

// Helper: create a mock Response with a body that provides a reader
function createMockResponse(
  status: number,
  chunks: Uint8Array[],
  textBody?: string,
): Response {
  if (status !== 200) {
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

// Helper: create a 200 response from SSE event objects
function createSSEResponse(...events: AgenticSSEEvent[]): Response {
  const text = events.map((e) => sseData(e)).join("");
  return createMockResponse(200, [encode(text)]);
}

// Mock fetch — jsdom doesn't provide globalThis.fetch
const mockFetch = jest.fn<
  Promise<Response>,
  [RequestInfo | URL, RequestInit?]
>();
global.fetch = mockFetch as typeof global.fetch;

beforeEach(() => {
  mockFetch.mockReset();
});

describe("fetch setup", () => {
  it("should POST with correct headers and credentials", async () => {
    mockFetch.mockResolvedValue(
      createSSEResponse({
        event: "complete",
        data: { result: "", validated: true },
      }),
    );

    await postAssistStream({ flow_id: "f1", input_value: "test" }, {});

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        credentials: "include",
        body: JSON.stringify({ flow_id: "f1", input_value: "test" }),
      }),
    );
  });

  it("should forward AbortSignal to fetch", async () => {
    const controller = new AbortController();
    mockFetch.mockResolvedValue(
      createSSEResponse({
        event: "complete",
        data: { result: "", validated: true },
      }),
    );

    await postAssistStream(
      { flow_id: "f1", input_value: "test" },
      {},
      controller.signal,
    );

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});

describe("event dispatch", () => {
  it("should dispatch onProgress for progress events", async () => {
    const progressEvent: AgenticProgressEvent = {
      event: "progress",
      step: "generating",
      attempt: 1,
      max_attempts: 4,
    };
    mockFetch.mockResolvedValue(
      createSSEResponse(progressEvent, {
        event: "complete",
        data: { result: "", validated: true },
      }),
    );

    const onProgress = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onProgress });

    expect(onProgress).toHaveBeenCalledWith(progressEvent);
  });

  it("should dispatch onToken for token events", async () => {
    const tokenEvent: AgenticTokenEvent = { event: "token", chunk: "Hello" };
    mockFetch.mockResolvedValue(
      createSSEResponse(tokenEvent, {
        event: "complete",
        data: { result: "", validated: true },
      }),
    );

    const onToken = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onToken });

    expect(onToken).toHaveBeenCalledWith(tokenEvent);
  });

  it("should dispatch onComplete and resolve", async () => {
    const completeEvent: AgenticCompleteEvent = {
      event: "complete",
      data: { result: "done", validated: true, class_name: "Test" },
    };
    mockFetch.mockResolvedValue(createSSEResponse(completeEvent));

    const onComplete = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onComplete });

    expect(onComplete).toHaveBeenCalledWith(completeEvent);
  });

  it("should dispatch onError for error events", async () => {
    const errorEvent: AgenticErrorEvent = {
      event: "error",
      message: "Rate limit",
    };
    mockFetch.mockResolvedValue(createSSEResponse(errorEvent));

    const onError = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onError });

    expect(onError).toHaveBeenCalledWith(errorEvent);
  });

  it("should dispatch onCancelled", async () => {
    const cancelledEvent: AgenticCancelledEvent = {
      event: "cancelled",
      message: "User cancelled",
    };
    mockFetch.mockResolvedValue(createSSEResponse(cancelledEvent));

    const onCancelled = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onCancelled });

    expect(onCancelled).toHaveBeenCalledWith(cancelledEvent);
  });

  it("should stop processing after terminal event", async () => {
    const completeEvent: AgenticCompleteEvent = {
      event: "complete",
      data: { result: "", validated: true },
    };
    const tokenAfter: AgenticTokenEvent = { event: "token", chunk: "ignored" };

    // Both events in same chunk — complete should stop processing
    const text = sseData(completeEvent) + sseData(tokenAfter);
    mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

    const onToken = jest.fn();
    const onComplete = jest.fn();
    await postAssistStream(
      { flow_id: "f1", input_value: "" },
      { onToken, onComplete },
    );

    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onToken).not.toHaveBeenCalled();
  });
});

describe("buffer handling", () => {
  it("should skip empty lines", async () => {
    // Stream with extra blank lines between events
    const text = `\n\ndata: ${JSON.stringify({ event: "complete", data: { result: "", validated: true } })}\n\n`;
    mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

    const onComplete = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onComplete });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("should skip malformed JSON without crashing", async () => {
    const text =
      `data: {not valid json}\n\n` +
      sseData({ event: "complete", data: { result: "", validated: true } });
    mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

    const onComplete = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onComplete });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("should_call_onError_when_sse_event_contains_malformed_json", async () => {
    // Bug: malformed JSON in SSE is silently discarded without notifying the UI.
    // The onError callback should fire so the user gets feedback.
    const text =
      `data: {not valid json}\n\n` +
      sseData({ event: "complete", data: { result: "", validated: true } });
    mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

    const onError = jest.fn();
    const onComplete = jest.fn();
    await postAssistStream(
      { flow_id: "f1", input_value: "" },
      { onError, onComplete },
    );

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({
        event: "error",
        message: expect.stringContaining("malformed"),
      }),
    );
    // Stream should continue processing after the malformed event
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("should reassemble data split across chunks", async () => {
    const fullLine = `data: ${JSON.stringify({ event: "token", chunk: "hello" })}\n\n`;
    // Split in the middle of the JSON
    const splitAt = Math.floor(fullLine.length / 2);
    const chunk1 = encode(fullLine.slice(0, splitAt));
    const chunk2 = encode(
      fullLine.slice(splitAt) +
        sseData({ event: "complete", data: { result: "", validated: true } }),
    );

    mockFetch.mockResolvedValue(createMockResponse(200, [chunk1, chunk2]));

    const onToken = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onToken });

    expect(onToken).toHaveBeenCalledWith({ event: "token", chunk: "hello" });
  });

  it("should process remaining buffer after stream ends", async () => {
    // Last line with no trailing newline
    const text = `data: ${JSON.stringify({ event: "complete", data: { result: "end", validated: true } })}`;
    mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

    const onComplete = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onComplete });

    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ event: "complete" }),
    );
  });
});

describe("error responses", () => {
  it("should call onError with JSON detail for non-200", async () => {
    mockFetch.mockResolvedValue(
      createMockResponse(400, [], JSON.stringify({ detail: "Bad request" })),
    );

    const onError = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onError });

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Bad request" }),
    );
  });

  it("should call onError with text for non-JSON error", async () => {
    mockFetch.mockResolvedValue(
      createMockResponse(500, [], "Internal Server Error"),
    );

    const onError = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onError });

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Internal Server Error" }),
    );
  });

  it("should call onError for null response body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      body: null,
    } as unknown as Response);

    const onError = jest.fn();
    await postAssistStream({ flow_id: "f1", input_value: "" }, { onError });

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "No response body" }),
    );
  });

  it("should not throw when callbacks are empty", async () => {
    mockFetch.mockResolvedValue(
      createSSEResponse({
        event: "complete",
        data: { result: "", validated: true },
      }),
    );

    // No callbacks at all — should not throw
    await expect(
      postAssistStream({ flow_id: "f1", input_value: "" }, {}),
    ).resolves.toBeUndefined();
  });
});

describe("bugs and edge cases", () => {
  it.failing(
    "BUG: should accept 'data:' without space (SSE spec allows no space after colon)",
    async () => {
      // SSE spec: "data:" is valid without trailing space.
      // L33: line.startsWith("data: ") requires space — "data:{json}" is silently dropped.
      const json = JSON.stringify({
        event: "complete",
        data: { result: "", validated: true },
      });
      const text = `data:${json}\n\n`;
      mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

      const onComplete = jest.fn();
      await postAssistStream(
        { flow_id: "f1", input_value: "" },
        { onComplete },
      );

      expect(onComplete).toHaveBeenCalledTimes(1);
    },
  );

  it.failing(
    "BUG: should reject events with wrong shape instead of casting",
    async () => {
      // L22: `JSON.parse(data) as AgenticSSEEvent` — no runtime validation.
      // A well-typed object that doesn't match any event type is accepted silently.
      const fakeEvent = { event: "unknown_type", foo: "bar" };
      const text = `data: ${JSON.stringify(fakeEvent)}\n\ndata: ${JSON.stringify({ event: "complete", data: { result: "", validated: true } })}\n\n`;
      mockFetch.mockResolvedValue(createMockResponse(200, [encode(text)]));

      const onError = jest.fn();
      await postAssistStream({ flow_id: "f1", input_value: "" }, { onError });

      // Should have reported an error for the unknown event type
      expect(onError).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringContaining("unknown"),
        }),
      );
    },
  );

  it("should_cancel_reader_before_releasing_lock_to_close_connection", async () => {
    // Bug: reader.releaseLock() without reader.cancel() — the underlying TCP
    // connection may remain open. Proper cleanup is cancel() then releaseLock().
    const cancelMock = jest.fn().mockResolvedValue(undefined);
    const releaseLockMock = jest.fn();

    const mockReader = {
      read: jest
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: encode(
            sseData({
              event: "complete",
              data: { result: "", validated: true },
            }),
          ),
        })
        .mockResolvedValue({ done: true, value: undefined }),
      cancel: cancelMock,
      releaseLock: releaseLockMock,
    };

    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => mockReader },
    } as unknown as Response);

    await postAssistStream(
      { flow_id: "f1", input_value: "" },
      { onComplete: jest.fn() },
    );

    // reader.cancel() should be called before releaseLock()
    expect(cancelMock).toHaveBeenCalled();
    expect(releaseLockMock).toHaveBeenCalled();
  });
});
