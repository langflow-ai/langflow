import { findPrimaryInput } from "../utils";

describe("Primary Input Identification", () => {
  describe("basic scenarios", () => {
    it("should identify first field with handle as primary input", () => {
      const templates = {
        text_input: { type: "str" },
        message_input: { type: "Message" },
        data_input: { type: "Data" },
      };

      const result = findPrimaryInput(
        ["text_input", "message_input", "data_input"],
        templates,
        false,
      );

      expect(result.primaryInputFieldName).toBe("message_input");
      expect(result.displayHandleMap.get("text_input")).toBe(false);
      expect(result.displayHandleMap.get("message_input")).toBe(true);
    });

    it("should return null when no fields have handles or empty fields", () => {
      const templates = { name: { type: "str" }, count: { type: "int" } };
      expect(
        findPrimaryInput(["name", "count"], templates, false)
          .primaryInputFieldName,
      ).toBeNull();
      expect(findPrimaryInput([], {}, false).primaryInputFieldName).toBeNull();
      expect(findPrimaryInput([], {}, false).displayHandleMap.size).toBe(0);
    });

    it("should respect field order when identifying primary input", () => {
      const templates = {
        secondary: { type: "Data" },
        primary: { type: "Message" },
      };

      expect(
        findPrimaryInput(["primary", "secondary"], templates, false)
          .primaryInputFieldName,
      ).toBe("primary");
      expect(
        findPrimaryInput(["secondary", "primary"], templates, false)
          .primaryInputFieldName,
      ).toBe("secondary");
    });
  });

  describe("filtering and tool mode", () => {
    it("should only process fields passed in shownTemplateFields array", () => {
      const templates = {
        hidden: { type: "Message" },
        visible: { type: "Data" },
      };

      const result = findPrimaryInput(["visible"], templates, false);
      expect(result.primaryInputFieldName).toBe("visible");
      expect(result.displayHandleMap.has("hidden")).toBe(false);
    });

    it("should handle tool_mode fields based on isToolMode flag", () => {
      const templates = {
        tool_field: { type: "Message", tool_mode: true },
        normal_field: { type: "Data" },
      };

      // Tool mode ON: tool_field shouldn't get handle
      const resultToolMode = findPrimaryInput(
        ["tool_field", "normal_field"],
        templates,
        true,
      );
      expect(resultToolMode.primaryInputFieldName).toBe("normal_field");
      expect(resultToolMode.displayHandleMap.get("tool_field")).toBe(false);

      // Tool mode OFF: tool_field should get handle
      expect(
        findPrimaryInput(["tool_field", "normal_field"], templates, false)
          .primaryInputFieldName,
      ).toBe("tool_field");
    });
  });

  describe("real-world component scenarios", () => {
    it("should handle LLM component with multiple inputs", () => {
      const templates = {
        model_name: { type: "str" },
        model: {
          type: "model",
          input_types: ["LanguageModel"],
          refresh_button: true,
        },
        temperature: { type: "float" },
        input_value: { type: "str", input_types: ["Message", "Text"] },
      };

      const result = findPrimaryInput(
        ["model_name", "model", "temperature", "input_value"],
        templates,
        false,
      );

      expect(result.primaryInputFieldName).toBe("model");
      expect(result.displayHandleMap.get("model_name")).toBe(false);
      expect(result.displayHandleMap.get("model")).toBe(true);
      expect(result.displayHandleMap.get("input_value")).toBe(true);
    });

    it("should handle components with only supported types (no handles)", () => {
      const templates = {
        api_key: { type: "str" },
        timeout: { type: "int" },
        enabled: { type: "bool" },
      };

      const result = findPrimaryInput(
        ["api_key", "timeout", "enabled"],
        templates,
        false,
      );
      expect(result.primaryInputFieldName).toBeNull();
      result.displayHandleMap.forEach((hasHandle) =>
        expect(hasHandle).toBe(false),
      );
    });
  });

  describe("edge cases", () => {
    it("should handle undefined template and refresh_button fields", () => {
      const templates = {
        valid: { type: "Message" },
        refreshable: { type: "Message", refresh_button: true },
        normal: { type: "Data" },
      };

      // Missing field should be skipped
      expect(
        findPrimaryInput(["missing", "valid"], templates, false)
          .primaryInputFieldName,
      ).toBe("valid");

      // refresh_button field shouldn't have handle
      const result = findPrimaryInput(
        ["refreshable", "normal"],
        templates,
        false,
      );
      expect(result.primaryInputFieldName).toBe("normal");
      expect(result.displayHandleMap.get("refreshable")).toBe(false);
    });
  });
});
