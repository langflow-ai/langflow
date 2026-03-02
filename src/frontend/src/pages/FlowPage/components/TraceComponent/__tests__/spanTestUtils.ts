import type { Span } from "../types";

/**
 * Shared factory for building test Span objects.
 * Provides a fully-populated default; pass overrides to customise per test.
 */
export const buildSpan = (overrides: Partial<Span> = {}): Span => ({
  id: "span-1",
  name: "Test Span",
  type: "llm",
  status: "ok",
  startTime: "2024-01-01T00:00:00Z",
  endTime: "2024-01-01T00:00:01Z",
  latencyMs: 1200,
  inputs: { foo: "bar" },
  outputs: { result: "ok" },
  error: undefined,
  modelName: "gpt-test",
  tokenUsage: {
    promptTokens: 10,
    completionTokens: 20,
    totalTokens: 30,
    cost: 0.5,
  },
  children: [],
  ...overrides,
});
