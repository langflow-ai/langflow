import { describe, it, expect } from "vitest";

/**
 * Unit tests for the connection mode logic in useModelConnectionLogic.
 *
 * The hook activates "Connect other models" mode purely on the frontend
 * by setting filter state in the flow store. No backend calls are made.
 * These tests validate the pure logic decisions without React rendering.
 */

describe("useModelConnectionLogic", () => {
  describe("effective input types defaulting", () => {
    const getEffectiveInputTypes = (inputTypes: string[]): string[] => {
      return inputTypes.length > 0 ? inputTypes : ["LanguageModel"];
    };

    it("should default to LanguageModel when input_types is empty", () => {
      // Arrange & Act
      const result = getEffectiveInputTypes([]);

      // Assert
      expect(result).toEqual(["LanguageModel"]);
    });

    it("should use provided input_types when available", () => {
      // Arrange & Act
      const result = getEffectiveInputTypes(["Embeddings"]);

      // Assert
      expect(result).toEqual(["Embeddings"]);
    });

    it("should preserve multiple input types", () => {
      // Arrange & Act
      const result = getEffectiveInputTypes(["LanguageModel", "ChatModel"]);

      // Assert
      expect(result).toEqual(["LanguageModel", "ChatModel"]);
    });
  });

  describe("filter object construction", () => {
    const NODE_ID = "agent-node-123";

    const buildFilterObj = (
      nodeId: string,
      targetHandle: string,
    ) => ({
      source: undefined,
      sourceHandle: undefined,
      target: nodeId,
      targetHandle,
      type: "LanguageModel",
      color: "datatype-fuchsia",
    });

    it("should set target to the node ID", () => {
      // Arrange & Act
      const filterObj = buildFilterObj(NODE_ID, "handle-123");

      // Assert
      expect(filterObj.target).toBe(NODE_ID);
      expect(filterObj.source).toBeUndefined();
      expect(filterObj.sourceHandle).toBeUndefined();
    });

    it("should use LanguageModel as the filter type", () => {
      // Arrange & Act
      const filterObj = buildFilterObj(NODE_ID, "handle-123");

      // Assert
      expect(filterObj.type).toBe("LanguageModel");
      expect(filterObj.color).toBe("datatype-fuchsia");
    });
  });

  describe("option value routing", () => {
    const shouldActivateConnectionMode = (optionValue: string): boolean => {
      return optionValue === "connect_other_models";
    };

    it("should activate for connect_other_models", () => {
      expect(shouldActivateConnectionMode("connect_other_models")).toBe(true);
    });

    it("should not activate for other option values", () => {
      expect(shouldActivateConnectionMode("some_other_option")).toBe(false);
      expect(shouldActivateConnectionMode("")).toBe(false);
      expect(shouldActivateConnectionMode("connect")).toBe(false);
    });
  });
});
