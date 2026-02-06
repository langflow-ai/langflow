import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import type { Edge } from "@xyflow/react";
import { findPrimaryInput } from "../utils";

// Helper to create a mock edge for testing
const createMockEdge = (
  nodeId: string,
  fieldName: string,
  template: { type?: string; input_types?: string[]; proxy?: any },
): Edge => {
  const handleId = scapedJSONStringfy(
    template.proxy
      ? {
          inputTypes: template.input_types,
          type: template.type,
          id: nodeId,
          fieldName,
          proxy: template.proxy,
        }
      : {
          inputTypes: template.input_types,
          type: template.type,
          id: nodeId,
          fieldName,
        },
  );

  return {
    id: `edge-${nodeId}-${fieldName}`,
    source: "source-node",
    target: nodeId,
    targetHandle: handleId,
  };
};

describe("Primary Input Identification", () => {
  const nodeId = "test-node-id";

  describe("basic scenarios", () => {
    it("should identify first connected field with handle as primary input", () => {
      const templates = {
        text_input: { type: "str" },
        message_input: { type: "Message" },
        data_input: { type: "Data" },
      };

      // Only message_input is connected
      const edges: Edge[] = [
        createMockEdge(nodeId, "message_input", templates.message_input),
      ];

      const result = findPrimaryInput(
        ["text_input", "message_input", "data_input"],
        templates,
        false,
        nodeId,
        edges,
      );

      expect(result.primaryInputFieldName).toBe("message_input");
      expect(result.displayHandleMap.get("text_input")).toBe(false);
      expect(result.displayHandleMap.get("message_input")).toBe(true);
    });

    it("should return null when no fields with handles are connected", () => {
      const templates = {
        message_input: { type: "Message" },
        data_input: { type: "Data" },
      };

      // No edges - nothing is connected
      const edges: Edge[] = [];

      const result = findPrimaryInput(
        ["message_input", "data_input"],
        templates,
        false,
        nodeId,
        edges,
      );

      // Still has handles, primary falls back to first handle field when nothing is connected
      expect(result.primaryInputFieldName).toBe("message_input");
      expect(result.displayHandleMap.get("message_input")).toBe(true);
      expect(result.displayHandleMap.get("data_input")).toBe(true);
    });

    it("should return null for empty fields", () => {
      expect(
        findPrimaryInput([], {}, false, nodeId, []).primaryInputFieldName,
      ).toBeNull();
      expect(
        findPrimaryInput([], {}, false, nodeId, []).displayHandleMap.size,
      ).toBe(0);
    });

    it("should respect field order when identifying primary input", () => {
      const templates = {
        secondary: { type: "Data" },
        primary: { type: "Message" },
      };

      // Both are connected
      const edges: Edge[] = [
        createMockEdge(nodeId, "primary", templates.primary),
        createMockEdge(nodeId, "secondary", templates.secondary),
      ];

      // First in order should be primary
      expect(
        findPrimaryInput(
          ["primary", "secondary"],
          templates,
          false,
          nodeId,
          edges,
        ).primaryInputFieldName,
      ).toBe("primary");
      expect(
        findPrimaryInput(
          ["secondary", "primary"],
          templates,
          false,
          nodeId,
          edges,
        ).primaryInputFieldName,
      ).toBe("secondary");
    });
  });

  describe("filtering and tool mode", () => {
    it("should only process fields passed in shownTemplateFields array", () => {
      const templates = {
        hidden: { type: "Message" },
        visible: { type: "Data" },
      };

      const edges: Edge[] = [
        createMockEdge(nodeId, "visible", templates.visible),
      ];

      const result = findPrimaryInput(
        ["visible"],
        templates,
        false,
        nodeId,
        edges,
      );
      expect(result.primaryInputFieldName).toBe("visible");
      expect(result.displayHandleMap.has("hidden")).toBe(false);
    });

    it("should handle tool_mode fields based on isToolMode flag", () => {
      const templates = {
        tool_field: { type: "Message", tool_mode: true },
        normal_field: { type: "Data" },
      };

      const edges: Edge[] = [
        createMockEdge(nodeId, "normal_field", templates.normal_field),
      ];

      // Tool mode ON: tool_field shouldn't get handle
      const resultToolMode = findPrimaryInput(
        ["tool_field", "normal_field"],
        templates,
        true,
        nodeId,
        edges,
      );
      expect(resultToolMode.primaryInputFieldName).toBe("normal_field");
      expect(resultToolMode.displayHandleMap.get("tool_field")).toBe(false);

      // Tool mode OFF: tool_field should get handle (but only if connected)
      const edgesWithToolField: Edge[] = [
        createMockEdge(nodeId, "tool_field", templates.tool_field),
      ];
      expect(
        findPrimaryInput(
          ["tool_field", "normal_field"],
          templates,
          false,
          nodeId,
          edgesWithToolField,
        ).primaryInputFieldName,
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

      // Connect input_value
      const edges: Edge[] = [
        createMockEdge(nodeId, "input_value", templates.input_value),
      ];

      const result = findPrimaryInput(
        ["model_name", "model", "temperature", "input_value"],
        templates,
        false,
        nodeId,
        edges,
      );

      // model type always shows handle, input_value is connected
      expect(result.primaryInputFieldName).toBe("input_value");
      expect(result.displayHandleMap.get("model_name")).toBe(false);
      expect(result.displayHandleMap.get("model")).toBe(true); // model type always shows handle
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
        nodeId,
        [],
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

      const edges: Edge[] = [
        createMockEdge(nodeId, "valid", templates.valid),
        createMockEdge(nodeId, "normal", templates.normal),
      ];

      // Missing field should be skipped
      expect(
        findPrimaryInput(["missing", "valid"], templates, false, nodeId, edges)
          .primaryInputFieldName,
      ).toBe("valid");

      // refresh_button field shouldn't have handle
      const result = findPrimaryInput(
        ["refreshable", "normal"],
        templates,
        false,
        nodeId,
        edges,
      );
      expect(result.primaryInputFieldName).toBe("normal");
      expect(result.displayHandleMap.get("refreshable")).toBe(false);
    });

    it("should pick first connected field even if later fields have handles", () => {
      const templates = {
        first: { type: "Message" },
        second: { type: "Data" },
        third: { type: "Message" },
      };

      // Only second field is connected
      const edges: Edge[] = [
        createMockEdge(nodeId, "second", templates.second),
      ];

      const result = findPrimaryInput(
        ["first", "second", "third"],
        templates,
        false,
        nodeId,
        edges,
      );

      // All have handles, but only second is connected
      expect(result.displayHandleMap.get("first")).toBe(true);
      expect(result.displayHandleMap.get("second")).toBe(true);
      expect(result.displayHandleMap.get("third")).toBe(true);
      expect(result.primaryInputFieldName).toBe("second");
    });
  });
});
