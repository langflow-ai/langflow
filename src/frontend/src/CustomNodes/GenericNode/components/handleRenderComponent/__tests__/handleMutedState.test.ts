/**
 * Unit tests for muted handle state in HandleRenderComponent.
 *
 * Model-type handles should be visually muted (invisible) when:
 * - No wire is connected to the handle
 * - No connection filter is active (drag/connection mode)
 *
 * They should be visible when:
 * - A wire is connected
 * - A connection filter is active (e.g., "Connect other models")
 * - The handle's own node initiated connection mode
 */

describe("model handle muted state", () => {
  describe("isMuted computation logic", () => {
    // Pure logic extracted from HandleRenderComponent useMemo
    const computeIsMuted = (
      idType: string | undefined,
      connectedEdge: boolean,
      filterPresent: boolean,
      isInConnectionMode: boolean = false,
    ): boolean => {
      const isModelType = idType === "model";
      return (
        isModelType && !connectedEdge && !filterPresent && !isInConnectionMode
      );
    };

    it("should be muted when model type has no connection, no filter, and not in connection mode", () => {
      // Arrange & Act
      const result = computeIsMuted("model", false, false, false);

      // Assert
      expect(result).toBe(true);
    });

    it("should not be muted when model type has a connected edge", () => {
      // Arrange & Act
      const result = computeIsMuted("model", true, false, false);

      // Assert
      expect(result).toBe(false);
    });

    it("should not be muted when model type has an active filter", () => {
      // Arrange & Act
      const result = computeIsMuted("model", false, true, false);

      // Assert
      expect(result).toBe(false);
    });

    it("should not be muted when model type has both connection and filter", () => {
      // Arrange & Act
      const result = computeIsMuted("model", true, true, false);

      // Assert
      expect(result).toBe(false);
    });

    it("should not be muted when in connection mode (Connect other models selected)", () => {
      // Arrange & Act — no edge, no filter, but connection mode is active
      const result = computeIsMuted("model", false, false, true);

      // Assert — handle must stay visible so user can drag a wire to it
      expect(result).toBe(false);
    });

    it("should never be muted for non-model types", () => {
      // Arrange & Act & Assert
      expect(computeIsMuted("str", false, false, false)).toBe(false);
      expect(computeIsMuted("Message", false, false, false)).toBe(false);
      expect(computeIsMuted(undefined, false, false, false)).toBe(false);
      expect(computeIsMuted("", false, false, false)).toBe(false);
    });
  });

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

  describe("muted handle visual styling", () => {
    // Pure logic extracted from HandleContent contentStyle useMemo
    const computeContentStyle = (
      isNullHandle: boolean,
      isMuted: boolean,
    ): { width: string; height: string; opacity: number } => {
      return {
        width: isMuted && !isNullHandle ? "6px" : "10px",
        height: isMuted && !isNullHandle ? "6px" : "10px",
        opacity: isMuted && !isNullHandle ? 0 : 1,
      };
    };

    it("should render invisible when muted and not null", () => {
      // Arrange & Act
      const style = computeContentStyle(false, true);

      // Assert
      expect(style.width).toBe("6px");
      expect(style.height).toBe("6px");
      expect(style.opacity).toBe(0);
    });

    it("should render full size when not muted and not null", () => {
      // Arrange & Act
      const style = computeContentStyle(false, false);

      // Assert
      expect(style.width).toBe("10px");
      expect(style.height).toBe("10px");
      expect(style.opacity).toBe(1);
    });

    it("should use null handle styling when isNullHandle overrides isMuted", () => {
      // isNullHandle takes priority — size stays 10px, opacity stays 1
      // (actual null handle styling uses different background/border, tested elsewhere)

      // Arrange & Act
      const style = computeContentStyle(true, true);

      // Assert
      expect(style.width).toBe("10px");
      expect(style.height).toBe("10px");
      expect(style.opacity).toBe(1);
    });
  });

  describe("muted handle neon shadow", () => {
    const computeNeonShadow = (
      isNullHandle: boolean,
      isMuted: boolean,
      isActive: boolean,
    ): string => {
      if (isNullHandle || isMuted) return "none";
      if (!isActive) return "ring";
      return "glow";
    };

    it("should return none when muted", () => {
      expect(computeNeonShadow(false, true, false)).toBe("none");
      expect(computeNeonShadow(false, true, true)).toBe("none");
    });

    it("should return none when null handle", () => {
      expect(computeNeonShadow(true, false, false)).toBe("none");
    });

    it("should return ring when not muted and not active", () => {
      expect(computeNeonShadow(false, false, false)).toBe("ring");
    });

    it("should return glow when not muted and active", () => {
      expect(computeNeonShadow(false, false, true)).toBe("glow");
    });
  });
});
