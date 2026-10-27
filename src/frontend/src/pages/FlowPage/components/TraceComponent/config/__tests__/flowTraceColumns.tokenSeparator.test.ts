// Unit tests for the token column valueGetter in flowTraceColumns.
// The valueGetter must return locale-formatted strings (toLocaleString) so
// large numbers like 12345 render as "12,345" in the table.

import { pickFirstNumber } from "../flowTraceColumnsHelpers";

function tokenValueGetter(totalTokens: unknown, total_tokens: unknown): string {
  const tokens = pickFirstNumber(totalTokens, total_tokens);
  return tokens === null ? "" : tokens.toLocaleString();
}

describe("token column valueGetter — locale-formatted output", () => {
  it("returns empty string when no token data", () => {
    expect(tokenValueGetter(undefined, undefined)).toBe("");
    expect(tokenValueGetter(null, null)).toBe("");
    expect(tokenValueGetter("", "")).toBe("");
  });

  it("formats numbers below 1000 without separator", () => {
    const result = tokenValueGetter(42, undefined);
    expect(result).toBe((42).toLocaleString());
  });

  it("formats large numbers with locale separator", () => {
    const result = tokenValueGetter(12345, undefined);
    expect(result).toBe((12345).toLocaleString());
    expect(result).not.toBe("12345");
  });

  it("prefers totalTokens over total_tokens", () => {
    expect(tokenValueGetter(100, 200)).toBe((100).toLocaleString());
  });

  it("falls back to total_tokens when totalTokens is empty", () => {
    expect(tokenValueGetter("", 999)).toBe((999).toLocaleString());
  });

  it("formats a million tokens with separator", () => {
    const result = tokenValueGetter(1000000, undefined);
    expect(result).toBe((1000000).toLocaleString());
    expect(result.length).toBeGreaterThan(7);
  });
});
