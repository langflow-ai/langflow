import { formatDate, formatTimestamp } from "../helpers";

describe("Memories helpers", () => {
  const originalToLocaleString = Date.prototype.toLocaleString;

  beforeAll(() => {
    // Force deterministic formatting regardless of machine locale/timezone.
    Date.prototype.toLocaleString = function (
      _locales?: Intl.LocalesArgument,
      options?: Intl.DateTimeFormatOptions,
    ) {
      return originalToLocaleString.call(this, "en-US", {
        ...(options ?? {}),
        timeZone: "UTC",
        hour12: false,
      });
    };
  });

  afterAll(() => {
    Date.prototype.toLocaleString = originalToLocaleString;
  });

  it("returns fallback values for empty dates", () => {
    expect(formatDate()).toBe("Never");
    expect(formatTimestamp()).toBe("-");
  });

  it("returns original value for invalid date strings", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
    expect(formatTimestamp("also-not-a-date")).toBe("also-not-a-date");
  });

  it("formats valid dates", () => {
    const date = formatDate("2025-01-15T10:30:00.000Z");
    // Include Z to avoid local-time parsing differences.
    const timestamp = formatTimestamp("2025-01-15   10:30:00Z");

    expect(date).toBe("Jan 15, 10:30");
    expect(timestamp).toBe("Jan 15, 10:30:00");
  });
});
