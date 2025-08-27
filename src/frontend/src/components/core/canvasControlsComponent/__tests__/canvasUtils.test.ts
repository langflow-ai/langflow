import { ReactFlowState } from "@xyflow/react";
import {
  formatZoomPercentage,
  getModifierKey,
  reactFlowSelector,
} from "../utils/canvasUtils";

// Mock the getOS utility
jest.mock("@/utils/utils", () => ({
  getOS: jest.fn(),
}));

import { getOS } from "@/utils/utils";

const mockGetOS = getOS as jest.MockedFunction<typeof getOS>;

describe("canvasUtils", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("getModifierKey", () => {
    it("returns ⌘ for macOS", () => {
      mockGetOS.mockReturnValue("macos");
      expect(getModifierKey()).toBe("⌘");
    });

    it("returns Ctrl for Windows", () => {
      mockGetOS.mockReturnValue("windows");
      expect(getModifierKey()).toBe("Ctrl");
    });

    it("returns Ctrl for Linux", () => {
      mockGetOS.mockReturnValue("linux");
      expect(getModifierKey()).toBe("Ctrl");
    });

    it("returns Ctrl for unknown OS", () => {
      mockGetOS.mockReturnValue("unknown");
      expect(getModifierKey()).toBe("Ctrl");
    });
  });

  describe("formatZoomPercentage", () => {
    it("formats zoom level 1 as 100%", () => {
      expect(formatZoomPercentage(1)).toBe("100%");
    });

    it("formats zoom level 0.5 as 50%", () => {
      expect(formatZoomPercentage(0.5)).toBe("50%");
    });

    it("formats zoom level 1.5 as 150%", () => {
      expect(formatZoomPercentage(1.5)).toBe("150%");
    });

    it("formats zoom level 0.25 as 25%", () => {
      expect(formatZoomPercentage(0.25)).toBe("25%");
    });

    it("formats zoom level 2.789 as 279%", () => {
      expect(formatZoomPercentage(2.789)).toBe("279%");
    });

    it("rounds decimal values correctly", () => {
      expect(formatZoomPercentage(0.333)).toBe("33%");
      expect(formatZoomPercentage(0.666)).toBe("67%");
      expect(formatZoomPercentage(1.234)).toBe("123%");
    });

    it("handles zero zoom level", () => {
      expect(formatZoomPercentage(0)).toBe("0%");
    });

    it("handles very small zoom levels", () => {
      expect(formatZoomPercentage(0.001)).toBe("0%");
      expect(formatZoomPercentage(0.005)).toBe("1%");
    });

    it("handles very large zoom levels", () => {
      expect(formatZoomPercentage(10)).toBe("1000%");
      expect(formatZoomPercentage(50.5)).toBe("5050%");
    });
  });

  describe("reactFlowSelector", () => {
    const createMockReactFlowState = (
      overrides: Partial<ReactFlowState> = {},
    ): ReactFlowState =>
      ({
        nodesDraggable: true,
        nodesConnectable: true,
        elementsSelectable: true,
        transform: [0, 0, 1], // x, y, zoom
        minZoom: 0.1,
        maxZoom: 5,
        ...overrides,
      }) as ReactFlowState;

    it("returns correct isInteractive when all interaction modes are enabled", () => {
      const state = createMockReactFlowState({
        nodesDraggable: true,
        nodesConnectable: true,
        elementsSelectable: true,
      });

      const result = reactFlowSelector(state);
      expect(result.isInteractive).toBe(true);
    });

    it("returns correct isInteractive when only nodesDraggable is enabled", () => {
      const state = createMockReactFlowState({
        nodesDraggable: true,
        nodesConnectable: false,
        elementsSelectable: false,
      });

      const result = reactFlowSelector(state);
      expect(result.isInteractive).toBe(true);
    });

    it("returns correct isInteractive when only nodesConnectable is enabled", () => {
      const state = createMockReactFlowState({
        nodesDraggable: false,
        nodesConnectable: true,
        elementsSelectable: false,
      });

      const result = reactFlowSelector(state);
      expect(result.isInteractive).toBe(true);
    });

    it("returns correct isInteractive when only elementsSelectable is enabled", () => {
      const state = createMockReactFlowState({
        nodesDraggable: false,
        nodesConnectable: false,
        elementsSelectable: true,
      });

      const result = reactFlowSelector(state);
      expect(result.isInteractive).toBe(true);
    });

    it("returns false for isInteractive when all interaction modes are disabled", () => {
      const state = createMockReactFlowState({
        nodesDraggable: false,
        nodesConnectable: false,
        elementsSelectable: false,
      });

      const result = reactFlowSelector(state);
      expect(result.isInteractive).toBe(false);
    });

    it("returns correct minZoomReached when zoom is at minimum", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 0.1], // zoom at minZoom
        minZoom: 0.1,
      });

      const result = reactFlowSelector(state);
      expect(result.minZoomReached).toBe(true);
    });

    it("returns correct minZoomReached when zoom is below minimum", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 0.05], // zoom below minZoom
        minZoom: 0.1,
      });

      const result = reactFlowSelector(state);
      expect(result.minZoomReached).toBe(true);
    });

    it("returns correct minZoomReached when zoom is above minimum", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 0.5], // zoom above minZoom
        minZoom: 0.1,
      });

      const result = reactFlowSelector(state);
      expect(result.minZoomReached).toBe(false);
    });

    it("returns correct maxZoomReached when zoom is at maximum", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 5], // zoom at maxZoom
        maxZoom: 5,
      });

      const result = reactFlowSelector(state);
      expect(result.maxZoomReached).toBe(true);
    });

    it("returns correct maxZoomReached when zoom is above maximum", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 10], // zoom above maxZoom
        maxZoom: 5,
      });

      const result = reactFlowSelector(state);
      expect(result.maxZoomReached).toBe(true);
    });

    it("returns correct maxZoomReached when zoom is below maximum", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 2], // zoom below maxZoom
        maxZoom: 5,
      });

      const result = reactFlowSelector(state);
      expect(result.maxZoomReached).toBe(false);
    });

    it("returns correct zoom level from transform", () => {
      const state = createMockReactFlowState({
        transform: [100, 200, 1.5], // x, y, zoom
      });

      const result = reactFlowSelector(state);
      expect(result.zoom).toBe(1.5);
    });

    it("handles edge case where zoom equals both min and max", () => {
      const state = createMockReactFlowState({
        transform: [0, 0, 1],
        minZoom: 1,
        maxZoom: 1,
      });

      const result = reactFlowSelector(state);
      expect(result.minZoomReached).toBe(true);
      expect(result.maxZoomReached).toBe(true);
      expect(result.zoom).toBe(1);
    });

    it("returns complete selector object with all properties", () => {
      const state = createMockReactFlowState({
        nodesDraggable: true,
        nodesConnectable: false,
        elementsSelectable: true,
        transform: [0, 0, 2],
        minZoom: 0.5,
        maxZoom: 4,
      });

      const result = reactFlowSelector(state);

      expect(result).toEqual({
        isInteractive: true,
        minZoomReached: false,
        maxZoomReached: false,
        zoom: 2,
      });
    });
  });
});
