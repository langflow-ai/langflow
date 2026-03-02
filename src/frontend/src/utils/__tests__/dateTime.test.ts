import { formatSmartTimestamp, parseApiTimestamp } from "../dateTime";

describe("dateTime", () => {
  describe("parseApiTimestamp", () => {
    it("returns null for null or undefined", () => {
      expect(parseApiTimestamp(null)).toBeNull();
      expect(parseApiTimestamp(undefined)).toBeNull();
    });

    it("returns the same Date instance when valid", () => {
      const date = new Date("2024-01-02T03:04:05Z");
      const result = parseApiTimestamp(date);
      expect(result).toBe(date);
    });

    it("returns null for invalid Date", () => {
      const invalid = new Date("not-a-date");
      expect(parseApiTimestamp(invalid)).toBeNull();
    });

    it("returns null for empty or whitespace string", () => {
      expect(parseApiTimestamp(" ")).toBeNull();
      expect(parseApiTimestamp("\n\t")).toBeNull();
    });

    it("preserves explicit timezone offset", () => {
      const result = parseApiTimestamp("2024-01-02T03:04:05+02:00");
      expect(result?.toISOString()).toBe("2024-01-02T01:04:05.000Z");
    });
  });

  describe("formatSmartTimestamp", () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date("2025-02-25T10:30:00Z"));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it("returns time for today", () => {
      const date = new Date("2025-02-25T08:15:00Z");
      const expected = new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        hour12: false,
        minute: "2-digit",
        second: "2-digit",
        timeZone: "UTC",
      }).format(date);
      expect(formatSmartTimestamp(date)).toBe(expected);
    });

    it("returns day/month for same year but not today", () => {
      const date = new Date("2025-01-05T08:15:00Z");
      const expected = new Intl.DateTimeFormat(undefined, {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        hour12: false,
        minute: "2-digit",
        second: "2-digit",
        timeZone: "UTC",
      }).format(date);
      expect(formatSmartTimestamp(date)).toBe(expected);
    });

    it("returns dd/mm/yyyy time for different year", () => {
      const date = new Date("2024-12-31T23:59:00Z");
      const time = new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        hour12: false,
        minute: "2-digit",
        second: "2-digit",
        timeZone: "UTC",
      }).format(date);
      expect(formatSmartTimestamp(date)).toBe(`31/12/2024 ${time}`);
    });

    it("returns original string for invalid input", () => {
      expect(formatSmartTimestamp("not-a-date")).toBe("not-a-date");
    });

    it("returns empty string for nullish input", () => {
      expect(formatSmartTimestamp(null)).toBe("");
      expect(formatSmartTimestamp(undefined)).toBe("");
    });
  });
});
