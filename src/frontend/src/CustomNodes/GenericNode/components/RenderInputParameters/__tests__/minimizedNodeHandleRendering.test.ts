describe("Minimized Node Handle Rendering", () => {
  const shouldRenderHandle = (
    showNode: boolean,
    displayHandle: boolean,
    isPrimaryInput: boolean,
  ): boolean => {
    // When minimized, only show handle for primary input with displayable handle
    if (!showNode) {
      return isPrimaryInput && displayHandle;
    }
    // When expanded, show based on displayHandle
    return displayHandle;
  };

  describe("when node is minimized (showNode = false)", () => {
    it("should render handle for primary input with displayHandle", () => {
      const result = shouldRenderHandle(false, true, true);
      expect(result).toBe(true);
    });

    it("should NOT render handle for non-primary input even with displayHandle", () => {
      const result = shouldRenderHandle(false, true, false);
      expect(result).toBe(false);
    });

    it("should NOT render handle for primary input without displayHandle", () => {
      const result = shouldRenderHandle(false, false, true);
      expect(result).toBe(false);
    });

    it("should NOT render handle for non-primary input without displayHandle", () => {
      const result = shouldRenderHandle(false, false, false);
      expect(result).toBe(false);
    });
  });

  describe("when node is expanded (showNode = true)", () => {
    it("should render handle when displayHandle is true (regardless of isPrimaryInput)", () => {
      expect(shouldRenderHandle(true, true, true)).toBe(true);
      expect(shouldRenderHandle(true, true, false)).toBe(true);
    });

    it("should NOT render handle when displayHandle is false", () => {
      expect(shouldRenderHandle(true, false, true)).toBe(false);
      expect(shouldRenderHandle(true, false, false)).toBe(false);
    });
  });

  describe("real-world scenarios", () => {
    it("should only show one handle when multiple inputs are minimized", () => {
      // Simulating a component with 3 Message inputs
      const inputs = [
        { name: "input1", displayHandle: true, isPrimaryInput: true },
        { name: "input2", displayHandle: true, isPrimaryInput: false },
        { name: "input3", displayHandle: true, isPrimaryInput: false },
      ];

      const minimized = true;
      const showNode = !minimized;

      const visibleHandles = inputs.filter((input) =>
        shouldRenderHandle(showNode, input.displayHandle, input.isPrimaryInput),
      );

      expect(visibleHandles.length).toBe(1);
      expect(visibleHandles[0].name).toBe("input1");
    });

    it("should show all handles when multiple inputs are expanded", () => {
      const inputs = [
        { name: "input1", displayHandle: true, isPrimaryInput: true },
        { name: "input2", displayHandle: true, isPrimaryInput: false },
        { name: "input3", displayHandle: true, isPrimaryInput: false },
      ];

      const minimized = false;
      const showNode = !minimized;

      const visibleHandles = inputs.filter((input) =>
        shouldRenderHandle(showNode, input.displayHandle, input.isPrimaryInput),
      );

      expect(visibleHandles.length).toBe(3);
    });

    it("should show no handles when minimized and no primary input exists", () => {
      // Component with only non-connectable inputs
      const inputs = [
        { name: "api_key", displayHandle: false, isPrimaryInput: false },
        { name: "temperature", displayHandle: false, isPrimaryInput: false },
      ];

      const showNode = false;

      const visibleHandles = inputs.filter((input) =>
        shouldRenderHandle(showNode, input.displayHandle, input.isPrimaryInput),
      );

      expect(visibleHandles.length).toBe(0);
    });

    it("should handle mixed inputs correctly when minimized", () => {
      // Some inputs have handles, some don't
      const inputs = [
        { name: "model_name", displayHandle: false, isPrimaryInput: false },
        { name: "model", displayHandle: true, isPrimaryInput: true }, // Primary
        { name: "temperature", displayHandle: false, isPrimaryInput: false },
        { name: "input_value", displayHandle: true, isPrimaryInput: false },
        { name: "system_message", displayHandle: true, isPrimaryInput: false },
      ];

      const showNode = false;

      const visibleHandles = inputs.filter((input) =>
        shouldRenderHandle(showNode, input.displayHandle, input.isPrimaryInput),
      );

      expect(visibleHandles.length).toBe(1);
      expect(visibleHandles[0].name).toBe("model");
    });
  });
});
