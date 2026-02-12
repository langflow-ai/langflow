import { formatSeconds } from "../format";

describe("formatSeconds", () => {
  it("should_format_values_under_1000ms_as_seconds", () => {
    expect(formatSeconds(500)).toBe("0.5s");
  });

  it("should_ceil_to_next_tenth_for_fractional_values", () => {
    expect(formatSeconds(500.3)).toBe("0.6s");
  });

  it("should_ceil_to_next_tenth_when_1000ms_or_above", () => {
    // 2113ms → ceil(2.113 * 10) / 10 = ceil(21.13) / 10 = 22 / 10 = 2.2
    expect(formatSeconds(2113)).toBe("2.2s");
  });

  it("should_keep_exact_tenths_unchanged", () => {
    expect(formatSeconds(2100)).toBe("2.1s");
  });

  it("should_ceil_small_fractions_above_a_tenth", () => {
    // 1001ms → ceil(1.001 * 10) / 10 = ceil(10.01) / 10 = 11 / 10 = 1.1
    expect(formatSeconds(1001)).toBe("1.1s");
  });

  it("should_format_values_under_1ms_as_seconds", () => {
    expect(formatSeconds(0.5)).toBe("0.1s");
  });

  it("should_handle_exact_1000ms_boundary", () => {
    expect(formatSeconds(1000)).toBe("1.0s");
  });

  it("should_handle_zero", () => {
    expect(formatSeconds(0)).toBe("0.0s");
  });
});
