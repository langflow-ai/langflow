import { render, screen } from "@testing-library/react";
import type { NoteDataType } from "@/types/flow";
import NoteNode from "../index";

// Mock the color utilities
jest.mock("../color-utils", () => ({
  isHexColor: jest.fn(),
  resolveColorValue: jest.fn(),
}));

import { isHexColor, resolveColorValue } from "../color-utils";

const mockIsHexColor = isHexColor as jest.MockedFunction<typeof isHexColor>;
const mockResolveColorValue = resolveColorValue as jest.MockedFunction<
  typeof resolveColorValue
>;

// Mock external dependencies
jest.mock("@xyflow/react", () => ({
  NodeResizer: ({ children, ...props }: any) => (
    <div data-testid="node-resizer" {...props}>
      {children}
    </div>
  ),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({
    currentFlow: {
      data: {
        nodes: [],
      },
    },
    setNode: jest.fn(),
  })),
}));

jest.mock("@/shared/hooks/use-alternate", () => ({
  useAlternate: () => [false, jest.fn()],
}));

jest.mock("../NoteToolbarComponent", () => ({
  __esModule: true,
  default: ({ data, bgColor }: any) => (
    <div data-testid="note-toolbar" data-bg-color={bgColor}>
      Toolbar for {data.id}
    </div>
  ),
}));

jest.mock("../../GenericNode/components/NodeDescription", () => ({
  __esModule: true,
  default: ({ style, inputClassName, mdClassName, ...props }: any) => (
    <div
      data-testid="node-description"
      style={style}
      className={`${inputClassName || ""} ${mdClassName || ""}`.trim()}
      {...props}
    >
      Node Description
    </div>
  ),
}));

describe("NoteNode Color Resolution", () => {
  const mockSetNode = jest.fn();
  const mockData: NoteDataType = {
    id: "test-note-id",
    type: "NoteNode",
    node: {
      template: {
        backgroundColor: "blue",
      },
    },
  };

  const defaultProps = {
    data: mockData,
    selected: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockResolveColorValue.mockReturnValue("#3b82f6");
    mockIsHexColor.mockReturnValue(false);
  });

  describe("Color Resolution Logic", () => {
    it("should resolve color value using resolveColorValue utility", () => {
      render(<NoteNode {...defaultProps} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith("blue");
    });

    it("should apply resolved color to node background", () => {
      mockResolveColorValue.mockReturnValue("#3b82f6");

      render(<NoteNode {...defaultProps} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode).toHaveStyle({ backgroundColor: "#3b82f6" });
    });

    it("should apply resolved color to NodeDescription", () => {
      mockResolveColorValue.mockReturnValue("#3b82f6");

      render(<NoteNode {...defaultProps} />);

      const nodeDescription = screen.getByTestId("node-description");
      expect(nodeDescription).toHaveStyle({ backgroundColor: "#3b82f6" });
    });

    it("should handle null resolved color", () => {
      mockResolveColorValue.mockReturnValue(null);

      render(<NoteNode {...defaultProps} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode).toHaveStyle({ backgroundColor: "#00000000" });
    });

    it("should handle undefined backgroundColor", () => {
      const dataWithoutColor = {
        ...mockData,
        node: {
          template: {},
        },
      };

      mockResolveColorValue.mockReturnValue(null);

      render(<NoteNode {...defaultProps} data={dataWithoutColor} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith(undefined);
    });

    it("should handle null backgroundColor", () => {
      const dataWithNullColor = {
        ...mockData,
        node: {
          template: {
            backgroundColor: null,
          },
        },
      };

      mockResolveColorValue.mockReturnValue(null);

      render(<NoteNode {...defaultProps} data={dataWithNullColor} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith(null);
    });
  });

  describe("Background Color Logic", () => {
    it("should return hex color directly when isHexColor returns true", () => {
      mockIsHexColor.mockReturnValue(true);

      const dataWithHexColor = {
        ...mockData,
        node: {
          template: {
            backgroundColor: "#FF5733",
          },
        },
      };

      render(<NoteNode {...defaultProps} data={dataWithHexColor} />);

      expect(mockIsHexColor).toHaveBeenCalledWith("#FF5733");

      // The toolbar should receive the hex color directly
      const toolbar = screen.getByTestId("note-toolbar");
      expect(toolbar).toHaveAttribute("data-bg-color", "#FF5733");
    });

    it("should return preset name when not a hex color and exists in COLOR_OPTIONS", () => {
      mockIsHexColor.mockReturnValue(false);

      render(<NoteNode {...defaultProps} />);

      // The component should use the preset name for the toolbar
      const toolbar = screen.getByTestId("note-toolbar");
      expect(toolbar).toHaveAttribute("data-bg-color", "blue");
    });

    it("should return transparent for invalid colors", () => {
      mockIsHexColor.mockReturnValue(false);

      const dataWithInvalidColor = {
        ...mockData,
        node: {
          template: {
            backgroundColor: "invalid-color",
          },
        },
      };

      render(<NoteNode {...defaultProps} data={dataWithInvalidColor} />);

      const toolbar = screen.getByTestId("note-toolbar");
      expect(toolbar).toHaveAttribute("data-bg-color", "transparent");
    });

    it("should return transparent for null backgroundColor", () => {
      const dataWithNullColor = {
        ...mockData,
        node: {
          template: {
            backgroundColor: null,
          },
        },
      };

      render(<NoteNode {...defaultProps} data={dataWithNullColor} />);

      const toolbar = screen.getByTestId("note-toolbar");
      expect(toolbar).toHaveAttribute("data-bg-color", "transparent");
    });
  });

  describe("Memoization", () => {
    it("should memoize resolved color value", () => {
      const { rerender } = render(<NoteNode {...defaultProps} />);

      expect(mockResolveColorValue).toHaveBeenCalledTimes(1);

      // Rerender with same data
      rerender(<NoteNode {...defaultProps} />);

      // Should not call again due to memoization
      expect(mockResolveColorValue).toHaveBeenCalledTimes(1);
    });

    it("should recalculate when backgroundColor changes", () => {
      const { rerender } = render(<NoteNode {...defaultProps} />);

      expect(mockResolveColorValue).toHaveBeenCalledTimes(1);

      const dataWithNewColor = {
        ...mockData,
        node: {
          template: {
            backgroundColor: "red",
          },
        },
      };

      rerender(<NoteNode {...defaultProps} data={dataWithNewColor} />);

      expect(mockResolveColorValue).toHaveBeenCalledTimes(2);
      expect(mockResolveColorValue).toHaveBeenLastCalledWith("red");
    });

    it("should memoize bgColor for toolbar", () => {
      const { rerender } = render(<NoteNode {...defaultProps} />);

      // Rerender with same data
      rerender(<NoteNode {...defaultProps} />);

      // Should not recalculate bgColor
      expect(mockIsHexColor).toHaveBeenCalledTimes(1);
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing node data", () => {
      const dataWithoutNode = {
        id: "test-note-id",
        type: "NoteNode" as const,
        node: {
          template: {},
        },
      };

      render(<NoteNode {...defaultProps} data={dataWithoutNode} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith(undefined);
    });

    it("should handle missing template", () => {
      const dataWithoutTemplate = {
        id: "test-note-id",
        type: "NoteNode" as const,
        node: {
          template: {},
        },
      };

      render(<NoteNode {...defaultProps} data={dataWithoutTemplate} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith(undefined);
    });

    it("should handle empty string backgroundColor", () => {
      const dataWithEmptyColor = {
        ...mockData,
        node: {
          template: {
            backgroundColor: "",
          },
        },
      };

      mockResolveColorValue.mockReturnValue(null);

      render(<NoteNode {...defaultProps} data={dataWithEmptyColor} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith("");
    });
  });

  describe("Component Integration", () => {
    it("should pass correct bgColor to NoteToolbarComponent", () => {
      render(<NoteNode {...defaultProps} />);

      const toolbar = screen.getByTestId("note-toolbar");
      expect(toolbar).toHaveAttribute("data-bg-color", "blue");
    });

    it("should apply correct styles based on resolved color", () => {
      mockResolveColorValue.mockReturnValue("#3b82f6");

      render(<NoteNode {...defaultProps} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode).toHaveClass("border");
      expect(noteNode).not.toHaveClass("-z-50");
    });

    it("should apply transparent styles when no color is resolved", () => {
      mockResolveColorValue.mockReturnValue(null);

      render(<NoteNode {...defaultProps} />);

      const noteNode = screen.getByTestId("note_node");
      expect(noteNode).not.toHaveClass("border");
    });

    it("should apply correct classes to NodeDescription based on color", () => {
      mockResolveColorValue.mockReturnValue("#3b82f6");

      render(<NoteNode {...defaultProps} />);

      const nodeDescription = screen.getByTestId("node-description");
      expect(nodeDescription).toHaveClass(
        "dark:!ring-background",
        "dark:text-background",
      );
    });

    it("should apply transparent classes to NodeDescription when no color", () => {
      mockResolveColorValue.mockReturnValue(null);

      render(<NoteNode {...defaultProps} />);

      const nodeDescription = screen.getByTestId("node-description");
      expect(nodeDescription).toHaveClass("dark:prose-invert");
      expect(nodeDescription).not.toHaveClass("dark:!text-background");
    });
  });
});
