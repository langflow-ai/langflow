/**
 * Unit tests for input-handle default-invisible behavior.
 *
 * Input (target / left-side) handles are invisible by default to reduce
 * canvas noise. They are revealed when ANY of these is true:
 * - the handle itself is hovered
 * - the node is selected (clicking a node selects it)
 * - the handle is connected to an edge
 * - a connection drag / filter is active (so the user can drop a wire)
 * - the node is in model connection mode
 *
 * Output (source / right-side) handles are never hidden by this rule and
 * keep their existing always-visible behavior.
 *
 * This generalizes the previous model-only "muted" behavior to every input
 * handle and additionally reveals on hover/selection.
 */

import {
  type InputHandleVisibilityState,
  isInputHandleHidden,
} from "../inputHandleVisibility";

const base: InputHandleVisibilityState = {
  left: true,
  isHovered: false,
  selected: false,
  hasConnectedEdge: false,
  filterPresent: false,
  isInConnectionMode: false,
};

describe("isInputHandleHidden", () => {
  it("should hide an input handle by default when nothing reveals it", () => {
    // Arrange & Act
    const result = isInputHandleHidden(base);

    // Assert
    expect(result).toBe(true);
  });

  it("should never hide an output (right-side) handle even when nothing reveals it", () => {
    // Arrange & Act
    const result = isInputHandleHidden({ ...base, left: false });

    // Assert
    expect(result).toBe(false);
  });

  it("should reveal the input handle when it is hovered", () => {
    // Arrange & Act
    const result = isInputHandleHidden({ ...base, isHovered: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should reveal the input handle when the node is selected", () => {
    // Arrange & Act
    const result = isInputHandleHidden({ ...base, selected: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should reveal the input handle when it is connected to an edge", () => {
    // Arrange & Act
    const result = isInputHandleHidden({ ...base, hasConnectedEdge: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should reveal the input handle while a connection drag/filter is active", () => {
    // Arrange & Act
    const result = isInputHandleHidden({ ...base, filterPresent: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should reveal the input handle while in model connection mode", () => {
    // Arrange & Act
    const result = isInputHandleHidden({ ...base, isInConnectionMode: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should keep an output handle visible regardless of any reveal flags", () => {
    // Arrange & Act — output handle, every reveal flag off
    const result = isInputHandleHidden({
      left: false,
      isHovered: false,
      selected: false,
      hasConnectedEdge: false,
      filterPresent: false,
      isInConnectionMode: false,
    });

    // Assert
    expect(result).toBe(false);
  });
});
