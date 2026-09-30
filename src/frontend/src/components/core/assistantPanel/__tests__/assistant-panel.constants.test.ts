import {
  ASSISTANT_PLACEHOLDERS,
  ASSISTANT_SESSION_STORAGE_KEY_PREFIX,
  ASSISTANT_TITLE,
  getAssistantPlaceholder,
} from "../assistant-panel.constants";

describe("assistant-panel.constants", () => {
  describe("ASSISTANT_TITLE", () => {
    it("should be Langflow Assistant", () => {
      expect(ASSISTANT_TITLE).toBe("Langflow Assistant");
    });
  });

  describe("ASSISTANT_SESSION_STORAGE_KEY_PREFIX", () => {
    it("should be a non-empty string", () => {
      expect(ASSISTANT_SESSION_STORAGE_KEY_PREFIX).toBeTruthy();
      expect(typeof ASSISTANT_SESSION_STORAGE_KEY_PREFIX).toBe("string");
    });

    it("should end with a separator for flow ID concatenation", () => {
      expect(ASSISTANT_SESSION_STORAGE_KEY_PREFIX).toMatch(/-$/);
    });
  });

  describe("ASSISTANT_PLACEHOLDERS", () => {
    it("should have at least 2 options for randomization", () => {
      expect(ASSISTANT_PLACEHOLDERS.length).toBeGreaterThanOrEqual(2);
    });

    it("should contain only non-empty strings", () => {
      for (const placeholder of ASSISTANT_PLACEHOLDERS) {
        expect(typeof placeholder).toBe("string");
        expect(placeholder.length).toBeGreaterThan(0);
      }
    });
  });

  describe("getAssistantPlaceholder", () => {
    it("should return a non-empty string", () => {
      const result = getAssistantPlaceholder();

      expect(typeof result).toBe("string");
      expect(result.length).toBeGreaterThan(0);
    });

    it("should return a value from the ASSISTANT_PLACEHOLDERS array", () => {
      const result = getAssistantPlaceholder();

      expect(ASSISTANT_PLACEHOLDERS).toContain(result);
    });

    it("should be callable multiple times without error", () => {
      const results = Array.from({ length: 10 }, () =>
        getAssistantPlaceholder(),
      );

      for (const result of results) {
        expect(ASSISTANT_PLACEHOLDERS).toContain(result);
      }
    });
  });
});
