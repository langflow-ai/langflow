import {
  convertSpan,
  convertTrace,
  sanitizeParams,
  sanitizeString,
} from "../helpers";
import type { SpanApiResponse, TraceApiResponse } from "../types";

describe("traces helpers", () => {
  describe("sanitizeString", () => {
    // Verifies that leading/trailing whitespace and embedded control characters (newline, tab) are stripped from the output.
    it("removes control characters and trims", () => {
      const value = "  hello\nworld\t";
      expect(sanitizeString(value)).toBe("helloworld");
    });

    // Verifies that the DEL character (U+007F) is treated as a non-printable and removed from the result.
    it("removes DEL character", () => {
      const value = "ok\u007f";
      expect(sanitizeString(value)).toBe("ok");
    });

    // Verifies that when a custom maxLen is provided, the output is truncated to that length even if input is longer.
    it("caps length to maxLen", () => {
      const value = "a".repeat(60);
      expect(sanitizeString(value, 10)).toBe("a".repeat(10));
    });

    // Verifies that a string containing only printable ASCII characters passes through unchanged.
    it("preserves printable characters", () => {
      const value = "abc-123_!";
      expect(sanitizeString(value)).toBe(value);
    });
  });

  describe("sanitizeParams", () => {
    // Verifies that string values in a params object are sanitized while number and boolean values are left unchanged.
    it("sanitizes string values only", () => {
      const result = sanitizeParams({
        query: "  hi\n",
        page: 2,
        active: true,
      });
      expect(result).toEqual({ query: "hi", page: 2, active: true });
    });

    // Verifies that non-string values (e.g., nested objects) are passed through without modification.
    it("keeps non-string objects intact", () => {
      const input = { nested: { a: 1 } };
      expect(sanitizeParams(input)).toEqual(input);
    });
  });

  describe("convertSpan", () => {
    // Verifies that a span with a nested child is correctly converted, preserving IDs and recursively mapping children.
    it("converts span and maps children", () => {
      const apiSpan: SpanApiResponse = {
        id: "root",
        name: "Root",
        type: "chain",
        status: "success",
        startTime: "2026-02-26T10:00:00Z",
        endTime: "2026-02-26T10:00:01Z",
        latencyMs: 1000,
        inputs: { input_value: "hello" },
        outputs: { result: "world" },
        error: undefined,
        modelName: "test-model",
        tokenUsage: {
          promptTokens: 1,
          completionTokens: 2,
          totalTokens: 3,
          cost: 0.01,
        },
        children: [
          {
            id: "child",
            name: "Child",
            type: "tool",
            status: "success",
            startTime: "2026-02-26T10:00:00Z",
            endTime: "2026-02-26T10:00:00Z",
            latencyMs: 100,
            inputs: {},
            outputs: {},
            error: undefined,
            modelName: "test-model",
            tokenUsage: {
              promptTokens: 1,
              completionTokens: 1,
              totalTokens: 2,
              cost: 0.001,
            },
            children: [],
          },
        ],
      };

      const result = convertSpan(apiSpan);

      expect(result.id).toBe("root");
      expect(result.children).toHaveLength(1);
      expect(result.children[0].id).toBe("child");
    });

    // Verifies that a span with no children results in an empty children array rather than undefined or null.
    it("defaults children to empty array", () => {
      const apiSpan: SpanApiResponse = {
        id: "solo",
        name: "Solo",
        type: "llm",
        status: "running",
        startTime: "2026-02-26T10:00:00Z",
        endTime: undefined,
        latencyMs: 10,
        inputs: {},
        outputs: {},
        error: undefined,
        modelName: undefined,
        tokenUsage: undefined,
        children: [],
      };

      const result = convertSpan(apiSpan);
      expect(result.children).toEqual([]);
    });
  });

  describe("convertTrace", () => {
    // Verifies that convertTrace returns null when the trace has an empty spans array, indicating no renderable data.
    it("returns null when spans are missing", () => {
      const apiTrace: TraceApiResponse = {
        id: "trace",
        name: "Trace",
        status: "success",
        startTime: "2026-02-26T10:00:00Z",
        endTime: undefined,
        totalLatencyMs: 100,
        totalTokens: 5,
        totalCost: 0.01,
        flowId: "flow",
        sessionId: "session",
        input: null,
        output: null,
        spans: [],
      };

      expect(convertTrace(apiTrace)).toBeNull();
    });

    // Verifies that a trace with at least one span is correctly converted, preserving trace ID and mapping all spans.
    it("converts trace with spans", () => {
      const apiTrace: TraceApiResponse = {
        id: "trace",
        name: "Trace",
        status: "success",
        startTime: "2026-02-26T10:00:00Z",
        endTime: undefined,
        totalLatencyMs: 100,
        totalTokens: 5,
        totalCost: 0.01,
        flowId: "flow",
        sessionId: "session",
        input: { input_value: "hello" },
        output: { result: "world" },
        spans: [
          {
            id: "span",
            name: "Span",
            type: "chain",
            status: "success",
            startTime: "2026-02-26T10:00:00Z",
            endTime: undefined,
            latencyMs: 100,
            inputs: {},
            outputs: {},
            error: undefined,
            modelName: "model",
            tokenUsage: {
              promptTokens: 1,
              completionTokens: 1,
              totalTokens: 2,
              cost: 0.001,
            },
            children: [],
          },
        ],
      };

      const result = convertTrace(apiTrace);

      expect(result?.id).toBe("trace");
      expect(result?.spans).toHaveLength(1);
      expect(result?.spans[0].id).toBe("span");
    });
  });
});
