import {
  convertSpan,
  convertTrace,
  sanitizeParams,
  sanitizeString,
} from "../helpers";
import type { SpanApiResponse, TraceApiResponse } from "../types";

describe("traces helpers", () => {
  describe("sanitizeString", () => {
    it("removes control characters and trims", () => {
      const value = "  hello\nworld\t";
      expect(sanitizeString(value)).toBe("helloworld");
    });

    it("removes DEL character", () => {
      const value = "ok\u007f";
      expect(sanitizeString(value)).toBe("ok");
    });

    it("caps length to maxLen", () => {
      const value = "a".repeat(60);
      expect(sanitizeString(value, 10)).toBe("a".repeat(10));
    });

    it("preserves printable characters", () => {
      const value = "abc-123_!";
      expect(sanitizeString(value)).toBe(value);
    });
  });

  describe("sanitizeParams", () => {
    it("sanitizes string values only", () => {
      const result = sanitizeParams({
        query: "  hi\n",
        page: 2,
        active: true,
      });
      expect(result).toEqual({ query: "hi", page: 2, active: true });
    });

    it("keeps non-string objects intact", () => {
      const input = { nested: { a: 1 } };
      expect(sanitizeParams(input)).toEqual(input);
    });
  });

  describe("convertSpan", () => {
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
