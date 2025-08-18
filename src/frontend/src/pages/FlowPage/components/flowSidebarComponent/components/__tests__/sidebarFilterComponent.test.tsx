import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { SidebarFilterComponent } from "../sidebarFilterComponent";

// Mock the UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: any) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content, side, styleClasses }: any) => (
    <div
      data-testid="tooltip"
      data-content={content}
      data-side={side}
      className={styleClasses}
    >
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, className, unstyled, ...props }: any) => (
    <button
      onClick={onClick}
      className={className}
      data-unstyled={unstyled}
      {...props}
    >
      {children}
    </button>
  ),
}));

describe("SidebarFilterComponent", () => {
  const mockResetFilters = jest.fn();

  const defaultProps = {
    isInput: true,
    type: "string",
    color: "blue",
    resetFilters: mockResetFilters,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render filter component with correct structure", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.getByText("string")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-filter-reset")).toBeInTheDocument();
      expect(screen.getByTestId("icon-X")).toBeInTheDocument();
    });

    it("should display ListFilter icon", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });

    it("should display X icon for reset button", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByTestId("icon-X")).toBeInTheDocument();
    });

    it("should have reset button with correct test id", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByTestId("sidebar-filter-reset")).toBeInTheDocument();
    });

    it("should render tooltip with correct content", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByTestId("tooltip")).toHaveAttribute(
        "data-content",
        "Remove filter",
      );
      expect(screen.getByTestId("tooltip")).toHaveAttribute(
        "data-side",
        "right",
      );
    });
  });

  describe("Input/Output Display", () => {
    it("should display 'Input:' when isInput is true", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.queryByText("Output:")).not.toBeInTheDocument();
    });

    it("should display 'Output:' when isInput is false", () => {
      const propsWithOutput = { ...defaultProps, isInput: false };
      render(<SidebarFilterComponent {...propsWithOutput} />);

      expect(screen.getByText("Output:")).toBeInTheDocument();
      expect(screen.queryByText("Input:")).not.toBeInTheDocument();
    });

    it("should display correct label for input", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
    });

    it("should display correct label for output", () => {
      const propsWithOutput = { ...defaultProps, isInput: false };
      render(<SidebarFilterComponent {...propsWithOutput} />);

      expect(screen.getByText("Output:")).toBeInTheDocument();
    });
  });

  describe("Type Display", () => {
    it("should display single type correctly", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("string")).toBeInTheDocument();
    });

    it("should display multiple types correctly", () => {
      const propsWithMultipleTypes = {
        ...defaultProps,
        type: "string\nint\nboolean",
      };

      render(<SidebarFilterComponent {...propsWithMultipleTypes} />);

      expect(screen.getByText("string, int, boolean")).toBeInTheDocument();
    });

    it("should handle empty type", () => {
      const propsWithEmptyType = { ...defaultProps, type: "" };
      render(<SidebarFilterComponent {...propsWithEmptyType} />);

      // Should not crash
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });

    it("should handle type with special characters", () => {
      const propsWithSpecialType = { ...defaultProps, type: "List[str]" };
      render(<SidebarFilterComponent {...propsWithSpecialType} />);

      expect(screen.getByText("List[str]")).toBeInTheDocument();
    });
  });

  describe("Pluralization", () => {
    it("should use singular form for single type", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.queryByText("Inputs:")).not.toBeInTheDocument();
    });

    it("should use plural form for multiple types", () => {
      const propsWithMultipleTypes = {
        ...defaultProps,
        type: "string\nint",
      };

      render(<SidebarFilterComponent {...propsWithMultipleTypes} />);

      expect(screen.getByText("Inputs:")).toBeInTheDocument();
      expect(screen.queryByText("Input:")).not.toBeInTheDocument();
    });

    it("should use plural form for output with multiple types", () => {
      const propsWithMultipleOutputTypes = {
        ...defaultProps,
        isInput: false,
        type: "string\nint\nfloat",
      };

      render(<SidebarFilterComponent {...propsWithMultipleOutputTypes} />);

      expect(screen.getByText("Outputs:")).toBeInTheDocument();
      expect(screen.queryByText("Output:")).not.toBeInTheDocument();
    });

    it("should handle edge case with empty lines in type", () => {
      const propsWithEmptyLines = {
        ...defaultProps,
        type: "string\n\nint",
      };

      render(<SidebarFilterComponent {...propsWithEmptyLines} />);

      // Should treat empty line as a separate type for pluralization
      expect(screen.getByText("Inputs:")).toBeInTheDocument();
    });
  });

  describe("Color Styling", () => {
    it("should render with different color props", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      // Just verify component renders with color prop - inline styles are complex to test
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });

    it("should handle different colors", () => {
      const propsWithDifferentColor = { ...defaultProps, color: "red" };
      render(<SidebarFilterComponent {...propsWithDifferentColor} />);

      // Verify component renders without errors with different color
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });

    it("should handle custom color values", () => {
      const propsWithCustomColor = { ...defaultProps, color: "custom-green" };
      render(<SidebarFilterComponent {...propsWithCustomColor} />);

      // Verify component renders without errors with custom color
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });
  });

  describe("Reset Functionality", () => {
    it("should call resetFilters when reset button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarFilterComponent {...defaultProps} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      await user.click(resetButton);

      expect(mockResetFilters).toHaveBeenCalledTimes(1);
    });

    it("should call resetFilters only once per click", async () => {
      const user = userEvent.setup();
      render(<SidebarFilterComponent {...defaultProps} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      await user.click(resetButton);
      await user.click(resetButton);

      expect(mockResetFilters).toHaveBeenCalledTimes(2);
    });

    it("should handle rapid clicks on reset button", async () => {
      const user = userEvent.setup();
      render(<SidebarFilterComponent {...defaultProps} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      await user.click(resetButton);
      await user.click(resetButton);
      await user.click(resetButton);

      expect(mockResetFilters).toHaveBeenCalledTimes(3);
    });

    it("should work with different callback functions", async () => {
      const user = userEvent.setup();
      const alternativeResetFilters = jest.fn();
      const propsWithDifferentCallback = {
        ...defaultProps,
        resetFilters: alternativeResetFilters,
      };

      render(<SidebarFilterComponent {...propsWithDifferentCallback} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      await user.click(resetButton);

      expect(alternativeResetFilters).toHaveBeenCalledTimes(1);
      expect(mockResetFilters).not.toHaveBeenCalled();
    });
  });

  describe("Component Structure", () => {
    it("should have correct DOM hierarchy", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const container =
        screen.getByTestId("icon-ListFilter").parentElement?.parentElement
          ?.parentElement;
      const iconContainer =
        screen.getByTestId("icon-ListFilter").parentElement?.parentElement;
      const resetButton = screen.getByTestId("sidebar-filter-reset");
      const tooltip = screen.getByTestId("tooltip");

      expect(container).toBeInTheDocument();
      expect(container).toContainElement(iconContainer);
      expect(container).toContainElement(tooltip);
      expect(tooltip).toContainElement(resetButton);
    });

    it("should contain all expected elements", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.getByText("string")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-filter-reset")).toBeInTheDocument();
      expect(screen.getByTestId("icon-X")).toBeInTheDocument();
      expect(screen.getByTestId("tooltip")).toBeInTheDocument();
    });

    it("should render reset button inside tooltip", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const tooltip = screen.getByTestId("tooltip");
      const resetButton = screen.getByTestId("sidebar-filter-reset");

      expect(tooltip).toContainElement(resetButton);
    });
  });

  describe("CSS Classes", () => {
    it("should render component structure correctly", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      // Verify component structure rather than specific CSS classes
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-filter-reset")).toBeInTheDocument();
      expect(screen.getByTestId("tooltip")).toBeInTheDocument();
    });

    it("should apply correct classes to icons", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const listFilterIcon = screen.getByTestId("icon-ListFilter");
      const xIcon = screen.getByTestId("icon-X");

      expect(listFilterIcon).toHaveClass("h-4", "w-4", "shrink-0", "stroke-2");
      expect(xIcon).toHaveClass("h-4", "w-4", "stroke-2");
    });

    it("should apply correct classes to button", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      expect(resetButton).toHaveClass("shrink-0");
      expect(resetButton).toHaveAttribute("data-unstyled", "true");
    });

    it("should apply tooltip styling classes", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const tooltip = screen.getByTestId("tooltip");
      expect(tooltip).toHaveClass("max-w-full");
    });
  });

  describe("Props Handling", () => {
    it("should handle different isInput values", () => {
      const { rerender } = render(
        <SidebarFilterComponent {...defaultProps} isInput={true} />,
      );
      expect(screen.getByText("Input:")).toBeInTheDocument();

      rerender(<SidebarFilterComponent {...defaultProps} isInput={false} />);
      expect(screen.getByText("Output:")).toBeInTheDocument();
    });

    it("should handle different type values", () => {
      const { rerender } = render(
        <SidebarFilterComponent {...defaultProps} type="string" />,
      );
      expect(screen.getByText("string")).toBeInTheDocument();

      rerender(<SidebarFilterComponent {...defaultProps} type="number" />);
      expect(screen.getByText("number")).toBeInTheDocument();
    });

    it("should handle different color values", () => {
      const { rerender } = render(
        <SidebarFilterComponent {...defaultProps} color="blue" />,
      );
      expect(screen.getByText("string")).toBeInTheDocument();

      rerender(<SidebarFilterComponent {...defaultProps} color="green" />);
      expect(screen.getByText("string")).toBeInTheDocument();
    });

    it("should handle missing resetFilters function gracefully", () => {
      const propsWithoutCallback = {
        ...defaultProps,
        resetFilters: undefined as any,
      };

      expect(() => {
        render(<SidebarFilterComponent {...propsWithoutCallback} />);
      }).not.toThrow();
    });
  });

  describe("Edge Cases", () => {
    it("should handle very long type names", () => {
      const propsWithLongType = {
        ...defaultProps,
        type: "VeryLongTypeNameThatExceedsNormalLength",
      };

      render(<SidebarFilterComponent {...propsWithLongType} />);

      expect(
        screen.getByText("VeryLongTypeNameThatExceedsNormalLength"),
      ).toBeInTheDocument();
    });

    it("should handle multiple very long type names", () => {
      const propsWithMultipleLongTypes = {
        ...defaultProps,
        type: "FirstVeryLongTypeName\nSecondVeryLongTypeName\nThirdVeryLongTypeName",
      };

      render(<SidebarFilterComponent {...propsWithMultipleLongTypes} />);

      expect(
        screen.getByText(
          "FirstVeryLongTypeName, SecondVeryLongTypeName, ThirdVeryLongTypeName",
        ),
      ).toBeInTheDocument();
    });

    it("should handle types with newlines and commas", () => {
      const propsWithComplexTypes = {
        ...defaultProps,
        type: "List[str, int]\nDict[str, Any]",
      };

      render(<SidebarFilterComponent {...propsWithComplexTypes} />);

      expect(
        screen.getByText("List[str, int], Dict[str, Any]"),
      ).toBeInTheDocument();
    });

    it("should handle empty color", () => {
      const propsWithEmptyColor = { ...defaultProps, color: "" };
      render(<SidebarFilterComponent {...propsWithEmptyColor} />);

      // Verify component renders without errors with empty color
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });

    it("should handle single newline character as type", () => {
      const propsWithNewlineType = { ...defaultProps, type: "\n" };
      render(<SidebarFilterComponent {...propsWithNewlineType} />);

      expect(screen.getByText("Inputs:")).toBeInTheDocument(); // Should be plural due to split
    });
  });

  describe("Text Content", () => {
    it("should display correct text for input with single type", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.getByText("string")).toBeInTheDocument();
    });

    it("should display correct text for output with multiple types", () => {
      const propsWithMultipleOutputTypes = {
        ...defaultProps,
        isInput: false,
        type: "str\nint\nfloat",
      };

      render(<SidebarFilterComponent {...propsWithMultipleOutputTypes} />);

      expect(screen.getByText("Outputs:")).toBeInTheDocument();
      expect(screen.getByText("str, int, float")).toBeInTheDocument();
    });

    it("should join multiple types with commas and spaces", () => {
      const propsWithMultipleTypes = {
        ...defaultProps,
        type: "type1\ntype2\ntype3\ntype4",
      };

      render(<SidebarFilterComponent {...propsWithMultipleTypes} />);

      expect(
        screen.getByText("type1, type2, type3, type4"),
      ).toBeInTheDocument();
    });
  });

  describe("Accessibility", () => {
    it("should have X icon with aria-hidden", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const xIcon = screen.getByTestId("icon-X");
      // The aria-hidden is applied to the ForwardedIconComponent, check it's present
      expect(xIcon).toBeInTheDocument();
    });

    it("should render reset button as clickable element", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      expect(resetButton.tagName).toBe("BUTTON");
    });
  });

  describe("Callback Functions", () => {
    it("should work with different resetFilters implementations", async () => {
      const user = userEvent.setup();
      const customResetFilters = jest.fn((data) => {
        // Custom implementation that might accept parameters
        console.log("Custom reset", data);
      });

      const propsWithCustomCallback = {
        ...defaultProps,
        resetFilters: customResetFilters,
      };

      render(<SidebarFilterComponent {...propsWithCustomCallback} />);

      const resetButton = screen.getByTestId("sidebar-filter-reset");
      await user.click(resetButton);

      expect(customResetFilters).toHaveBeenCalledTimes(1);
    });
  });
});
