import {
  formatDelta,
  formatDuration,
  formatPercent,
  formatScore,
  formatTokenCount,
  formatUsd,
} from "../utils/format";

describe("evals formatting", () => {
  it("should show a dash, never a guessed number, when a value is unknown", () => {
    expect(formatUsd(null)).toBe("—");
    expect(formatUsd(undefined)).toBe("—");
    expect(formatTokenCount(null)).toBe("—");
    expect(formatPercent(null)).toBe("—");
    expect(formatScore(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });

  it("should keep sub-cent costs visible", () => {
    expect(formatUsd(0.0004)).toContain("0.0004");
    expect(formatUsd(1.5)).toContain("1.50");
    expect(formatUsd(0)).toContain("0.00");
  });

  it("should format durations in ms or seconds", () => {
    expect(formatDuration(250)).toBe("250 ms");
    expect(formatDuration(1500)).toBe("1.5 s");
  });

  it("should give a signed delta only when both totals exist", () => {
    expect(formatDelta(138, 100)).toBe("+38%");
    expect(formatDelta(96, 100)).toBe("-4%");
    expect(formatDelta(100, 100)).toBe("0%");
    expect(formatDelta(100, null)).toBeNull();
    expect(formatDelta(0, 100)).toBeNull();
  });
});
