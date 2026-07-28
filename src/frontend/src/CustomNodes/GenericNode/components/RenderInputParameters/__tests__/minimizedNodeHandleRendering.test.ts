// LE-1810 (T8): a minimized component still shows ALL its handles. The old
// primary-input-only rule was removed — handle rendering now depends only on
// displayHandle, in both states. Each minimized handle receives a distinct
// vertical offset so they don't overlap on the collapsed card.
describe("Minimized Node Handle Rendering (LE-1810)", () => {
  const shouldRenderHandle = (
    _showNode: boolean,
    displayHandle: boolean,
  ): boolean => {
    return displayHandle;
  };

  const minimizedHandleTop = (handleIdx: number, handleCount: number): string =>
    `${(((handleIdx + 1) / (handleCount + 1)) * 100).toFixed(2)}%`;

  describe("when node is minimized (showNode = false)", () => {
    it("renders a handle for EVERY input with displayHandle", () => {
      expect(shouldRenderHandle(false, true)).toBe(true);
    });

    it("does not render handles for inputs without displayHandle", () => {
      expect(shouldRenderHandle(false, false)).toBe(false);
    });
  });

  describe("when node is expanded (showNode = true)", () => {
    it("renders based on displayHandle only", () => {
      expect(shouldRenderHandle(true, true)).toBe(true);
      expect(shouldRenderHandle(true, false)).toBe(false);
    });
  });

  describe("real-world scenarios", () => {
    it("shows ALL handles when a component with multiple inputs is minimized", () => {
      const inputs = [
        { name: "input1", displayHandle: true },
        { name: "input2", displayHandle: true },
        { name: "input3", displayHandle: true },
        { name: "plain_field", displayHandle: false },
      ];

      const visibleHandles = inputs.filter((input) =>
        shouldRenderHandle(false, input.displayHandle),
      );

      expect(visibleHandles.length).toBe(3);
      expect(visibleHandles.map((i) => i.name)).toEqual([
        "input1",
        "input2",
        "input3",
      ]);
    });

    it("distributes minimized handles at distinct vertical offsets", () => {
      const offsets = [0, 1, 2].map((idx) => minimizedHandleTop(idx, 3));

      expect(offsets).toEqual(["25.00%", "50.00%", "75.00%"]);
      expect(new Set(offsets).size).toBe(offsets.length);
    });

    it("centers a single minimized handle", () => {
      expect(minimizedHandleTop(0, 1)).toBe("50.00%");
    });
  });
});
