/**
 * Tests for assistant panel message helpers.
 *
 * Tests randomized message functions used for reasoning/validation UI states.
 */

import {
  getRandomPlaceholderMessage,
  getRandomReasoningHeader,
  getRandomReasoningMessages,
  getRandomThinkingMessage,
  getRandomValidationMessages,
} from "../messages";

describe("getRandomReasoningMessages", () => {
  it("should return all expected keys", () => {
    const result = getRandomReasoningMessages();

    expect(result).toHaveProperty("analyzing");
    expect(result).toHaveProperty("identifyingInputs");
    expect(result).toHaveProperty("checkingDependencies");
    expect(result).toHaveProperty("generatingCode");
  });

  it("should return non-empty strings for all values", () => {
    const result = getRandomReasoningMessages();

    for (const value of Object.values(result)) {
      expect(typeof value).toBe("string");
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it("should return varied results across multiple calls", () => {
    const results = new Set<string>();
    for (let i = 0; i < 50; i++) {
      const msg = getRandomReasoningMessages();
      results.add(msg.analyzing);
    }
    // 8 variations — 50 calls should produce at least 2 unique values
    expect(results.size).toBeGreaterThanOrEqual(2);
  });
});

describe("getRandomValidationMessages", () => {
  it("should return all expected keys", () => {
    const result = getRandomValidationMessages();

    expect(result).toHaveProperty("validating");
    expect(result).toHaveProperty("validationFailed");
    expect(result).toHaveProperty("retrying");
  });

  it("should return non-empty strings for all values", () => {
    const result = getRandomValidationMessages();

    for (const value of Object.values(result)) {
      expect(typeof value).toBe("string");
      expect(value.length).toBeGreaterThan(0);
    }
  });
});

describe("getRandomReasoningHeader", () => {
  it("should return a non-empty string ending with '...'", () => {
    const result = getRandomReasoningHeader();

    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
    expect(result).toMatch(/\.\.\.$/);
  });
});

describe("getRandomThinkingMessage", () => {
  it("should return from same pool as reasoning header", () => {
    // Both use REASONING_HEADER_MESSAGES — deterministic with Math.random = 0
    const spy = jest.spyOn(Math, "random").mockReturnValue(0);
    const header = getRandomReasoningHeader();
    const thinking = getRandomThinkingMessage();
    spy.mockRestore();

    expect(header).toBe(thinking);
  });
});

describe("getRandomPlaceholderMessage", () => {
  it("should return from same pool as reasoning header", () => {
    const spy = jest.spyOn(Math, "random").mockReturnValue(0);
    const header = getRandomReasoningHeader();
    const placeholder = getRandomPlaceholderMessage();
    spy.mockRestore();

    expect(header).toBe(placeholder);
  });
});

describe("deterministic Math.random", () => {
  it("should return first element when Math.random is 0", () => {
    const spy = jest.spyOn(Math, "random").mockReturnValue(0);
    const result = getRandomReasoningHeader();
    spy.mockRestore();

    // Math.floor(0 * 8) = 0 → first element "Thinking..."
    expect(result).toBe("Thinking...");
  });

  it("should return last element when Math.random is 0.999", () => {
    const spy = jest.spyOn(Math, "random").mockReturnValue(0.999);
    const result = getRandomReasoningHeader();
    spy.mockRestore();

    // Math.floor(0.999 * 8) = Math.floor(7.992) = 7 → last element "Almost there..."
    expect(result).toBe("Almost there...");
  });
});
