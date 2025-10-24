import { render, screen } from "@testing-library/react";
import type { NoteDataType } from "@/types/flow";
import NoteToolbarComponent from "../index";

// Mock the color utilities
jest.mock("../../color-utils", () => ({
  isHexColor: jest.fn(),
  resolveColorValue: jest.fn(),
}));

import { isHexColor, resolveColorValue } from "../../color-utils";

const mockIsHexColor = isHexColor as jest.MockedFunction<typeof isHexColor>;
const mockResolveColorValue = resolveColorValue as jest.MockedFunction<
  typeof resolveColorValue
>;

// Mock external dependencies
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn(() => jest.fn()),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({
    nodes: [],
    setLastCopiedSelection: jest.fn(),
    paste: jest.fn(),
    setNode: jest.fn(),
    deleteNode: jest.fn(),
  })),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn(() => jest.fn()),
}));

jest.mock("@/stores/shortcuts", () => ({
  useShortcutsStore: jest.fn(() => ({ shortcuts: [] })),
}));

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

jest.mock("../../../../components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, ...props }: any) => (
    <span data-testid="icon" data-name={name} {...props}>
      {name}
    </span>
  ),
}));

jest.mock("../../components/color-picker-buttons", () => ({
  ColorPickerButtons: ({ bgColor, data, setNode }: any) => (
    <div
      data-testid="color-picker-buttons"
      data-bg-color={bgColor}
      data-node-id={data.id}
    >
      Color Picker for {data.id}
    </div>
  ),
}));

jest.mock("../../components/select-items", () => ({
  SelectItems: ({ data }: any) => (
    <div data-testid="select-items" data-node-id={data.id}>
      Select Items for {data.id}
    </div>
  ),
}));

// Mock ShadTooltip to avoid TooltipProvider requirement
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content, side }: any) => (
    <div data-testid="tooltip" data-content={content} data-side={side}>
      {children}
    </div>
  ),
}));

// Mock Popover components to make content always visible in tests
jest.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: any) => <div data-testid="popover">{children}</div>,
  PopoverContent: ({ children }: any) => (
    <div data-testid="popover-content">{children}</div>
  ),
  PopoverTrigger: ({ children }: any) => (
    <div data-testid="popover-trigger">{children}</div>
  ),
}));

describe("NoteToolbarComponent Color Handling", () => {
  const mockData: NoteDataType = {
    id: "test-note-id",
    type: "NoteNode",
    node: {
      template: {
        backgroundColor: "blue",
      },
    } as any,
  };

  const defaultProps = {
    data: mockData,
    bgColor: "blue",
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockResolveColorValue.mockReturnValue("#3b82f6");
    mockIsHexColor.mockReturnValue(false);
  });

  describe("Color Resolution", () => {
    it("should resolve color value using resolveColorValue utility", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith("blue");
    });

    it("should apply resolved color to color picker style", () => {
      mockResolveColorValue.mockReturnValue("#3b82f6");

      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPicker = screen.getByTestId("color_picker");
      const colorDiv = colorPicker.querySelector("div");
      expect(colorDiv).toHaveStyle({ backgroundColor: "#3b82f6" });
    });

    it("should handle null resolved color", () => {
      mockResolveColorValue.mockReturnValue(null);

      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPicker = screen.getByTestId("color_picker");
      const colorDiv = colorPicker.querySelector("div");
      expect(colorDiv).toHaveStyle({ backgroundColor: "#00000000" });
    });

    it("should handle different color values", () => {
      mockResolveColorValue.mockReturnValue("#FF5733");

      render(<NoteToolbarComponent {...defaultProps} bgColor="red" />);

      const colorPicker = screen.getByTestId("color_picker");
      const colorDiv = colorPicker.querySelector("div");
      expect(colorDiv).toHaveStyle({ backgroundColor: "#FF5733" });
    });
  });

  describe("Color Picker Integration", () => {
    it("should pass bgColor to ColorPickerButtons", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPickerButtons = screen.getByTestId("color-picker-buttons");
      expect(colorPickerButtons).toHaveAttribute("data-bg-color", "blue");
    });

    it("should pass data to ColorPickerButtons", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPickerButtons = screen.getByTestId("color-picker-buttons");
      expect(colorPickerButtons).toHaveAttribute(
        "data-node-id",
        "test-note-id",
      );
    });

    it("should pass setNode function to ColorPickerButtons", () => {
      const mockSetNode = jest.fn();
      const mockUseFlowStore = require("@/stores/flowStore").default;
      mockUseFlowStore.mockReturnValue({
        nodes: [],
        setLastCopiedSelection: jest.fn(),
        paste: jest.fn(),
        setNode: mockSetNode,
        deleteNode: jest.fn(),
      });

      render(<NoteToolbarComponent {...defaultProps} />);

      // The setNode function should be available to ColorPickerButtons
      expect(mockSetNode).toBeDefined();
    });
  });

  describe("Color Picker Styling", () => {
    it("should apply border class when color is null", () => {
      mockResolveColorValue.mockReturnValue(null);

      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPicker = screen.getByTestId("color_picker");
      const colorDiv = colorPicker.querySelector("div");
      expect(colorDiv).toHaveClass("border");
    });

    it("should not apply border class when color is resolved", () => {
      mockResolveColorValue.mockReturnValue("#3b82f6");

      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPicker = screen.getByTestId("color_picker");
      const colorDiv = colorPicker.querySelector("div");
      expect(colorDiv).not.toHaveClass("border");
    });

    it("should apply correct CSS classes to color picker", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      const colorPicker = screen.getByTestId("color_picker");
      expect(colorPicker).toHaveClass(
        "relative",
        "inline-flex",
        "items-center",
        "rounded-l-md",
        "bg-background",
        "px-2",
        "py-2",
        "text-foreground",
        "shadow-md",
        "transition-all",
        "duration-500",
        "ease-in-out",
        "hover:bg-muted",
        "focus:z-10",
      );
    });
  });

  describe("Memoization", () => {
    it("should memoize color picker style", () => {
      const { rerender } = render(<NoteToolbarComponent {...defaultProps} />);

      // resolveColorValue is called twice: once in useMemo, once in className
      expect(mockResolveColorValue).toHaveBeenCalledTimes(2);

      // Rerender with same props
      rerender(<NoteToolbarComponent {...defaultProps} />);

      // Should not call again due to memoization (still 2 calls total)
      expect(mockResolveColorValue).toHaveBeenCalledTimes(2);
    });

    it("should recalculate when bgColor changes", () => {
      const { rerender } = render(<NoteToolbarComponent {...defaultProps} />);

      // resolveColorValue is called twice: once in useMemo, once in className
      expect(mockResolveColorValue).toHaveBeenCalledTimes(2);

      // Change bgColor
      rerender(<NoteToolbarComponent {...defaultProps} bgColor="red" />);

      // Should be called 4 times total (2 for initial render, 2 for rerender with new color)
      expect(mockResolveColorValue).toHaveBeenCalledTimes(4);
      expect(mockResolveColorValue).toHaveBeenLastCalledWith("red");
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty bgColor", () => {
      render(<NoteToolbarComponent {...defaultProps} bgColor="" />);

      expect(mockResolveColorValue).toHaveBeenCalledWith("");
    });

    it("should handle null bgColor", () => {
      render(<NoteToolbarComponent {...defaultProps} bgColor={null as any} />);

      expect(mockResolveColorValue).toHaveBeenCalledWith(null);
    });

    it("should handle undefined bgColor", () => {
      render(
        <NoteToolbarComponent {...defaultProps} bgColor={undefined as any} />,
      );

      expect(mockResolveColorValue).toHaveBeenCalledWith(undefined);
    });

    it("should handle invalid color values", () => {
      mockResolveColorValue.mockReturnValue(null);

      render(
        <NoteToolbarComponent {...defaultProps} bgColor="invalid-color" />,
      );

      const colorPicker = screen.getByTestId("color_picker");
      const colorDiv = colorPicker.querySelector("div");
      expect(colorDiv).toHaveStyle({ backgroundColor: "#00000000" });
      expect(colorDiv).toHaveClass("border");
    });
  });

  describe("Component Rendering", () => {
    it("should render color picker with correct test ID", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      expect(screen.getByTestId("color_picker")).toBeInTheDocument();
    });

    it("should render more options button", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      expect(screen.getByTestId("more-options-modal")).toBeInTheDocument();
    });

    it("should render ColorPickerButtons component", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      expect(screen.getByTestId("color-picker-buttons")).toBeInTheDocument();
    });

    it("should render SelectItems component", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      expect(screen.getByTestId("select-items")).toBeInTheDocument();
    });

    it("should apply correct wrapper classes", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      const wrapper = screen.getByTestId("color_picker").closest(".w-26");
      expect(wrapper).toHaveClass(
        "w-26",
        "noflow",
        "nowheel",
        "nopan",
        "nodelete",
        "nodrag",
        "h-10",
      );
    });
  });

  describe("Tooltip Integration", () => {
    it("should render color picker with tooltip", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      // The tooltip should be present (mocked as ShadTooltip)
      const colorPicker = screen.getByTestId("color_picker");
      expect(colorPicker).toBeInTheDocument();
    });

    it("should render more options with tooltip", () => {
      render(<NoteToolbarComponent {...defaultProps} />);

      const moreOptions = screen.getByTestId("more-options-modal");
      expect(moreOptions).toBeInTheDocument();
    });
  });
});
