import { formatAverageChunkSize, formatNumber } from "../knowledgeBaseUtils";

describe("knowledgeBaseUtils", () => {
  describe("formatNumber", () => {
    it("formats numbers with commas for thousands", () => {
      expect(formatNumber(1000)).toBe("1,000");
      expect(formatNumber(1500)).toBe("1,500");
      expect(formatNumber(10000)).toBe("10,000");
      expect(formatNumber(100000)).toBe("100,000");
      expect(formatNumber(1000000)).toBe("1,000,000");
    });

    it("handles numbers less than 1000 without commas", () => {
      expect(formatNumber(0)).toBe("0");
      expect(formatNumber(1)).toBe("1");
      expect(formatNumber(99)).toBe("99");
      expect(formatNumber(999)).toBe("999");
    });

    it("handles negative numbers", () => {
      expect(formatNumber(-1000)).toBe("-1,000");
      expect(formatNumber(-1500)).toBe("-1,500");
      expect(formatNumber(-999)).toBe("-999");
    });

    it("handles decimal numbers by displaying them with decimals", () => {
      expect(formatNumber(1000.5)).toBe("1,000.5");
      expect(formatNumber(1999.9)).toBe("1,999.9");
      expect(formatNumber(999.1)).toBe("999.1");
    });

    it("handles very large numbers", () => {
      expect(formatNumber(1234567890)).toBe("1,234,567,890");
      expect(formatNumber(987654321)).toBe("987,654,321");
    });
  });

  describe("formatAverageChunkSize", () => {
    it("formats average chunk size by rounding and formatting", () => {
      expect(formatAverageChunkSize(1000.4)).toBe("1,000");
      expect(formatAverageChunkSize(1000.6)).toBe("1,001");
      expect(formatAverageChunkSize(2500)).toBe("2,500");
      expect(formatAverageChunkSize(999.9)).toBe("1,000");
    });

    it("handles small decimal values", () => {
      expect(formatAverageChunkSize(1.2)).toBe("1");
      expect(formatAverageChunkSize(1.6)).toBe("2");
      expect(formatAverageChunkSize(0.4)).toBe("0");
      expect(formatAverageChunkSize(0.6)).toBe("1");
    });

    it("handles zero and negative values", () => {
      expect(formatAverageChunkSize(0)).toBe("0");
      expect(formatAverageChunkSize(-5.5)).toBe("-5");
      expect(formatAverageChunkSize(-1000.4)).toBe("-1,000");
    });

    it("handles large decimal values", () => {
      expect(formatAverageChunkSize(123456.7)).toBe("123,457");
      expect(formatAverageChunkSize(999999.1)).toBe("999,999");
      expect(formatAverageChunkSize(999999.9)).toBe("1,000,000");
    });

    it("handles edge cases", () => {
      expect(formatAverageChunkSize(0.5)).toBe("1");
      expect(formatAverageChunkSize(-0.5)).toBe("-0");
      expect(formatAverageChunkSize(Number.MAX_SAFE_INTEGER)).toBe(
        "9,007,199,254,740,991",
      );
    });
  });
});
