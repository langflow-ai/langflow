/**
 * Unit tests for model-connection-mode logic in HandleRenderComponent.
 *
 * NOTE: The previous model-only "muted" handle behavior has been generalized
 * into the default-collapsed (small) input-handle behavior. The size decision
 * now lives in `isInputHandleCollapsed` and is covered by
 * `inputHandleVisibility.test.ts`. This file retains only the
 * `isOwnModelConnectionMode` logic, which is still computed in
 * HandleRenderComponent to keep a model handle visible while its own node
 * initiated connection mode.
 */

describe("model handle connection mode", () => {
  describe("isOwnModelConnectionMode logic", () => {
    // Pure logic extracted from HandleRenderComponent useMemo
    const computeIsOwnModelConnectionMode = (
      idType: string | undefined,
      left: boolean,
      filterTargetNodeId: string | undefined,
      nodeId: string,
    ): boolean => {
      return idType === "model" && left && filterTargetNodeId === nodeId;
    };

    const NODE_ID = "agent-node-123";

    it("should be true when filter targets this node's model input handle", () => {
      // Arrange & Act
      const result = computeIsOwnModelConnectionMode(
        "model",
        true,
        NODE_ID,
        NODE_ID,
      );

      // Assert
      expect(result).toBe(true);
    });

    it("should be false when filter targets a different node", () => {
      // Arrange & Act
      const result = computeIsOwnModelConnectionMode(
        "model",
        true,
        "other-node-456",
        NODE_ID,
      );

      // Assert
      expect(result).toBe(false);
    });

    it("should be false for non-model types", () => {
      // Arrange & Act
      const result = computeIsOwnModelConnectionMode(
        "str",
        true,
        NODE_ID,
        NODE_ID,
      );

      // Assert
      expect(result).toBe(false);
    });

    it("should be false for right-side (output) handles", () => {
      // Arrange & Act
      const result = computeIsOwnModelConnectionMode(
        "model",
        false,
        NODE_ID,
        NODE_ID,
      );

      // Assert
      expect(result).toBe(false);
    });

    it("should be false when no filter is active", () => {
      // Arrange & Act
      const result = computeIsOwnModelConnectionMode(
        "model",
        true,
        undefined,
        NODE_ID,
      );

      // Assert
      expect(result).toBe(false);
    });
  });
});
