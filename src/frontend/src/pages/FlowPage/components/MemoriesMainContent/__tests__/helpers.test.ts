import {
  formatDate,
  formatTimestamp,
  statusBgColors,
  statusColors,
} from "../helpers";

describe("Memories helpers", () => {
  it("returns fallback values for empty dates", () => {
    expect(formatDate()).toBe("Never");
    expect(formatTimestamp()).toBe("-");
  });

  it("returns original value for invalid date strings", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
    expect(formatTimestamp("also-not-a-date")).toBe("also-not-a-date");
  });

  it("formats valid dates", () => {
    // Use a fixed date and verify exact format
    const date = formatDate("2025-01-15T10:30:00.000Z");
    const timestamp = formatTimestamp("2025-01-15 10:30:00");

    // formatDate: "Jan 15, 05:30 AM" — month + day + time, no year
    expect(date).toMatch(/Jan\s+\d{1,2},?\s+\d{1,2}:\d{2}/);
    // formatTimestamp: "Jan 15, 05:30:00 AM" — same but with seconds
    expect(timestamp).toMatch(/Jan\s+\d{1,2},?\s+\d{1,2}:\d{2}:\d{2}/);
    // Or use snapshot testing:
    // expect(date).toMatchSnapshot();
    // expect(timestamp).toMatchSnapshot();
  });

  it("exposes expected status color mappings", () => {
    expect(statusColors.failed).toBe("text-destructive");
    expect(statusBgColors.generating).toBe("bg-primary/10");
  });
});
