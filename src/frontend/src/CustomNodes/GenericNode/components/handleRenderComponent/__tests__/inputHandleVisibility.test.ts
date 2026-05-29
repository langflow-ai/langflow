/**
 * Unit tests for input-handle collapsed (small) default behavior.
 *
 * Input (target / left-side) handles render as a small collapsed dot by
 * default to reduce canvas noise. They grow to full size when ANY of these is
 * true:
 * - the handle itself is hovered
 * - the node is selected (clicking a node selects it)
 * - the handle is connected to an edge
 * - a connection drag / filter is active (so the user can drop a wire)
 * - the node is in model connection mode
 *
 * Output (source / right-side) handles are never collapsed by this rule and
 * keep their existing full-size behavior.
 */

import {
  type InputHandleVisibilityState,
  isInputHandleCollapsed,
} from "../inputHandleVisibility";

const base: InputHandleVisibilityState = {
  left: true,
  isHovered: false,
  selected: false,
  hasConnectedEdge: false,
  filterPresent: false,
  isInConnectionMode: false,
};

describe("isInputHandleCollapsed", () => {
  it("should collapse an input handle by default when nothing reveals it", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed(base);

    // Assert
    expect(result).toBe(true);
  });

  it("should never collapse an output (right-side) handle even when nothing reveals it", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed({ ...base, left: false });

    // Assert
    expect(result).toBe(false);
  });

  it("should expand the input handle when it is hovered", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed({ ...base, isHovered: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should expand the input handle when the node is selected", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed({ ...base, selected: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should expand the input handle when it is connected to an edge", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed({ ...base, hasConnectedEdge: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should expand the input handle while a connection drag/filter is active", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed({ ...base, filterPresent: true });

    // Assert
    expect(result).toBe(false);
  });

  it("should expand the input handle while in model connection mode", () => {
    // Arrange & Act
    const result = isInputHandleCollapsed({
      ...base,
      isInConnectionMode: true,
    });

    // Assert
    expect(result).toBe(false);
  });

  it("should keep an output handle full size regardless of any reveal flags", () => {
    // Arrange & Act — output handle, every reveal flag off
    const result = isInputHandleCollapsed({
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
