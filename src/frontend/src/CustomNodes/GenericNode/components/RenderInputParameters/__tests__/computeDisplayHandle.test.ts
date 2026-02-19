/**
 * Unit tests for computeDisplayHandle function
 *
 * This function determines whether a node input field should display a connection handle.
 * It's used to identify which inputs can accept connections from other nodes.
 */

import { computeDisplayHandle } from "../utils";

describe("computeDisplayHandle", () => {
  describe("type handling", () => {
    it("should return false for all LANGFLOW_SUPPORTED_TYPES without input_types", () => {
      const supportedTypes = [
        "str",
        "bool",
        "float",
        "code",
        "prompt",
        "mustache",
        "file",
        "int",
        "dict",
        "NestedDict",
        "table",
        "link",
        "slider",
        "tab",
        "sortableList",
        "connect",
        "auth",
        "query",
        "mcp",
        "tools",
      ];

      supportedTypes.forEach((type) => {
        expect(computeDisplayHandle({ type }, false)).toBe(false);
      });
    });

    it("should return true for unsupported types", () => {
      ["Message", "Data", "Document", "BaseLLM", "CustomType"].forEach(
        (type) => {
          expect(computeDisplayHandle({ type }, false)).toBe(true);
        },
      );
    });

    it("should return true for empty or undefined type", () => {
      expect(computeDisplayHandle({ type: "" }, false)).toBe(true);
      expect(computeDisplayHandle({}, false)).toBe(true);
    });
  });

  describe("input_types handling", () => {
    it("should return true when input_types has values, even for supported types", () => {
      expect(
        computeDisplayHandle({ type: "str", input_types: ["Message"] }, false),
      ).toBe(true);
      expect(
        computeDisplayHandle(
          { type: "Message", input_types: ["Document"] },
          false,
        ),
      ).toBe(true);
    });

    it("should return false when input_types is empty array", () => {
      expect(
        computeDisplayHandle({ type: "str", input_types: [] }, false),
      ).toBe(false);
    });
  });

  describe("tool mode handling", () => {
    it("should return false only when both isToolMode and template.tool_mode are true", () => {
      expect(
        computeDisplayHandle({ type: "Message", tool_mode: true }, true),
      ).toBe(false);
      expect(
        computeDisplayHandle({ type: "Message", tool_mode: true }, false),
      ).toBe(true);
      expect(
        computeDisplayHandle({ type: "Message", tool_mode: false }, true),
      ).toBe(true);
      expect(computeDisplayHandle({ type: "Message" }, true)).toBe(true);
    });
  });

  describe("refresh button handling", () => {
    it("should return false when refresh_button is true for non-model types", () => {
      expect(
        computeDisplayHandle({ type: "Message", refresh_button: true }, false),
      ).toBe(false);
      expect(
        computeDisplayHandle({ type: "Message", refresh_button: false }, false),
      ).toBe(true);
      expect(computeDisplayHandle({ type: "Message" }, false)).toBe(true);
    });
  });

  describe("model input handling", () => {
    it("should always show handle for model type", () => {
      expect(computeDisplayHandle({ type: "model" }, false)).toBe(true);
      expect(
        computeDisplayHandle({ type: "model", input_types: [] }, false),
      ).toBe(true);
      expect(
        computeDisplayHandle(
          { type: "model", input_types: ["LanguageModel"] },
          false,
        ),
      ).toBe(true);
    });

    it("should always show handle for model type even with refresh_button", () => {
      expect(
        computeDisplayHandle(
          {
            type: "model",
            refresh_button: true,
            input_types: ["LanguageModel"],
          },
          false,
        ),
      ).toBe(true);
      expect(
        computeDisplayHandle({ type: "model", refresh_button: true }, false),
      ).toBe(true);
    });
  });

  describe("real-world scenarios", () => {
    it("should handle LLM component inputs correctly", () => {
      // Model selector always shows handle
      expect(
        computeDisplayHandle(
          {
            type: "model",
            input_types: ["LanguageModel"],
            refresh_button: true,
          },
          false,
        ),
      ).toBe(true);
      // Model selector without input_types also shows handle
      expect(
        computeDisplayHandle(
          {
            type: "model",
            refresh_button: true,
          },
          false,
        ),
      ).toBe(true);
      // Text input with optional connection
      expect(
        computeDisplayHandle(
          { type: "str", input_types: ["Message", "Text"] },
          false,
        ),
      ).toBe(true);
      // Pure string input
      expect(computeDisplayHandle({ type: "str" }, false)).toBe(false);
    });

    it("should handle tool mode component correctly", () => {
      expect(
        computeDisplayHandle({ type: "Message", tool_mode: true }, true),
      ).toBe(false);
      expect(
        computeDisplayHandle({ type: "Message", tool_mode: false }, true),
      ).toBe(true);
    });

    it("should return false when multiple blocking conditions exist", () => {
      expect(
        computeDisplayHandle(
          { type: "str", tool_mode: true, refresh_button: true },
          true,
        ),
      ).toBe(false);
    });
  });
});
