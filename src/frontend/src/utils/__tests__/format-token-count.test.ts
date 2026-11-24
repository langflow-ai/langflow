import { formatTokenCount } from "../format-token-count";

describe("formatTokenCount", () => {
  it("returns null for null input", () => {
    expect(formatTokenCount(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(formatTokenCount(undefined)).toBeNull();
  });

  it("returns null for zero", () => {
    expect(formatTokenCount(0)).toBeNull();
  });

  it("returns null for negative numbers", () => {
    expect(formatTokenCount(-100)).toBeNull();
  });

  it("returns plain number for counts under 1000", () => {
    expect(formatTokenCount(1)).toBe("1");
    expect(formatTokenCount(500)).toBe("500");
    expect(formatTokenCount(999)).toBe("999");
  });

  it("formats thousands with K suffix", () => {
    expect(formatTokenCount(1000)).toBe("1K");
    expect(formatTokenCount(1500)).toBe("1.5K");
    expect(formatTokenCount(2500)).toBe("2.5K");
    expect(formatTokenCount(10000)).toBe("10K");
    expect(formatTokenCount(999999)).toBe("1000.0K");
  });

  it("formats millions with M suffix", () => {
    expect(formatTokenCount(1000000)).toBe("1M");
    expect(formatTokenCount(1500000)).toBe("1.5M");
    expect(formatTokenCount(2500000)).toBe("2.5M");
  });

  it("drops decimal when it is zero", () => {
    expect(formatTokenCount(2000)).toBe("2K");
    expect(formatTokenCount(3000000)).toBe("3M");
  });
});
