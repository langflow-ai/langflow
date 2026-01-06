/**
 * Unit tests for NoteNode shrink/resize behavior
 * Validates that sticky notes can shrink to the correct minimum size
 */

import { render, screen } from "@testing-library/react";
import {
  DEFAULT_NOTE_SIZE,
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import type { NoteDataType } from "@/types/flow";

// Mock dependencies
const mockSetNode = jest.fn();
const mockCurrentFlow = {
  data: {
    nodes: [] as Array<{ id: string; width?: number; height?: number }>,
  },
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: any) => any) =>
    selector({
      currentFlow: mockCurrentFlow,
      setNode: mockSetNode,
    }),
}));

jest.mock("@xyflow/react", () => ({
  NodeResizer: ({
    minWidth,
    minHeight,
    onResize,
    isVisible,
  }: {
    minWidth: number;
    minHeight: number;
    onResize: (event: any, params: { width: number; height: number }) => void;
    isVisible?: boolean;
  }) => (
    <div
      data-testid="node-resizer"
      data-min-width={minWidth}
      data-min-height={minHeight}
      data-is-visible={isVisible}
    />
  ),
}));

jest.mock("@/shared/hooks/use-alternate", () => ({
  useAlternate: (initial: boolean) => [initial, jest.fn()],
}));

jest.mock("../NoteToolbarComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="note-toolbar" />,
}));

jest.mock("../../GenericNode/components/NodeDescription", () => ({
  __esModule: true,
  default: () => <div data-testid="node-description" />,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

// Import component after mocks are set up
import NoteNode from "../index";

describe("NoteNode Shrink Behavior", () => {
  const createMockData = (
    id: string = "test-note",
    backgroundColor: string = "amber",
  ): NoteDataType =>
    ({
      id,
      type: "noteNode",
      node: {
        description: "Test note content",
        template: { backgroundColor },
      },
    }) as NoteDataType;

  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentFlow.data.nodes = [];
  });

  describe("Minimum Size Constraints", () => {
    it("should configure NodeResizer with correct minimum width", () => {
      const data = createMockData();
      render(<NoteNode data={data} selected={true} />);

      const resizer = screen.getByTestId("node-resizer");
      expect(Number(resizer.dataset.minWidth)).toBe(NOTE_NODE_MIN_WIDTH);
      expect(NOTE_NODE_MIN_WIDTH).toBe(260);
    });

    it("should configure NodeResizer with correct minimum height", () => {
      const data = createMockData();
      render(<NoteNode data={data} selected={true} />);

      const resizer = screen.getByTestId("node-resizer");
      expect(Number(resizer.dataset.minHeight)).toBe(NOTE_NODE_MIN_HEIGHT);
      expect(NOTE_NODE_MIN_HEIGHT).toBe(100);
    });

    it("should show resizer only when selected", () => {
      const data = createMockData();

      // When selected
      const { rerender } = render(<NoteNode data={data} selected={true} />);
      let resizer = screen.getByTestId("node-resizer");
      expect(resizer.dataset.isVisible).toBe("true");

      // When not selected
      rerender(<NoteNode data={data} selected={false} />);
      resizer = screen.getByTestId("node-resizer");
      expect(resizer.dataset.isVisible).toBe("false");
    });
  });

  describe("Default Size Behavior", () => {
    it("should use DEFAULT_NOTE_SIZE when no dimensions are stored", () => {
      const data = createMockData("note-1");
      mockCurrentFlow.data.nodes = [];

      render(<NoteNode data={data} selected={false} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode.style.width).toBe(`${DEFAULT_NOTE_SIZE}px`);
      expect(noteNode.style.height).toBe(`${DEFAULT_NOTE_SIZE}px`);
      expect(DEFAULT_NOTE_SIZE).toBe(324);
    });

    it("should use stored dimensions from flow state", () => {
      const data = createMockData("note-1");
      const customWidth = 400;
      const customHeight = 300;

      mockCurrentFlow.data.nodes = [
        { id: "note-1", width: customWidth, height: customHeight },
      ];

      render(<NoteNode data={data} selected={false} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode.style.width).toBe(`${customWidth}px`);
      expect(noteNode.style.height).toBe(`${customHeight}px`);
    });
  });

  describe("Shrink to Minimum Size", () => {
    it("should allow shrinking to minimum dimensions", () => {
      const data = createMockData("note-1");

      // Simulate a note that has been shrunk to minimum size
      mockCurrentFlow.data.nodes = [
        {
          id: "note-1",
          width: NOTE_NODE_MIN_WIDTH,
          height: NOTE_NODE_MIN_HEIGHT,
        },
      ];

      render(<NoteNode data={data} selected={true} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode.style.width).toBe(`${NOTE_NODE_MIN_WIDTH}px`);
      expect(noteNode.style.height).toBe(`${NOTE_NODE_MIN_HEIGHT}px`);
    });

    it("should render correctly at minimum width", () => {
      const data = createMockData("note-1");
      mockCurrentFlow.data.nodes = [
        { id: "note-1", width: NOTE_NODE_MIN_WIDTH, height: DEFAULT_NOTE_SIZE },
      ];

      render(<NoteNode data={data} selected={false} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode.style.width).toBe(`${NOTE_NODE_MIN_WIDTH}px`);
    });

    it("should render correctly at minimum height", () => {
      const data = createMockData("note-1");
      mockCurrentFlow.data.nodes = [
        {
          id: "note-1",
          width: DEFAULT_NOTE_SIZE,
          height: NOTE_NODE_MIN_HEIGHT,
        },
      ];

      render(<NoteNode data={data} selected={false} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode.style.height).toBe(`${NOTE_NODE_MIN_HEIGHT}px`);
    });
  });

  describe("Size Constraints Validation", () => {
    it("should have minimum width less than default size", () => {
      expect(NOTE_NODE_MIN_WIDTH).toBeLessThan(DEFAULT_NOTE_SIZE);
    });

    it("should have minimum height less than default size", () => {
      expect(NOTE_NODE_MIN_HEIGHT).toBeLessThan(DEFAULT_NOTE_SIZE);
    });

    it("should have reasonable minimum dimensions for usability", () => {
      // Minimum width should be at least 200px for readability
      expect(NOTE_NODE_MIN_WIDTH).toBeGreaterThanOrEqual(200);
      // Minimum height should be at least 80px for content
      expect(NOTE_NODE_MIN_HEIGHT).toBeGreaterThanOrEqual(80);
    });
  });
});
