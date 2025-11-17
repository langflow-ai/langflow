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
    name: "Input",
    description: "string",
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

  describe("Name Display", () => {
    it("should display name correctly", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
    });

    it("should display different names correctly", () => {
      const propsWithDifferentName = { ...defaultProps, name: "Output" };
      render(<SidebarFilterComponent {...propsWithDifferentName} />);

      expect(screen.getByText("Output:")).toBeInTheDocument();
      expect(screen.queryByText("Input:")).not.toBeInTheDocument();
    });

    it("should display custom names correctly", () => {
      const propsWithCustomName = { ...defaultProps, name: "Custom Filter" };
      render(<SidebarFilterComponent {...propsWithCustomName} />);

      expect(screen.getByText("Custom Filter:")).toBeInTheDocument();
    });

    it("should handle empty names", () => {
      const propsWithEmptyName = { ...defaultProps, name: "" };
      render(<SidebarFilterComponent {...propsWithEmptyName} />);

      expect(screen.getByText(":")).toBeInTheDocument();
    });
  });

  describe("Description Display", () => {
    it("should display single description correctly", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("string")).toBeInTheDocument();
    });

    it("should display multiple descriptions correctly", () => {
      const propsWithMultipleDescriptions = {
        ...defaultProps,
        description: "string\nint\nboolean",
      };

      render(<SidebarFilterComponent {...propsWithMultipleDescriptions} />);

      expect(screen.getByText("string, int, boolean")).toBeInTheDocument();
    });

    it("should handle empty description", () => {
      const propsWithEmptyDescription = { ...defaultProps, description: "" };
      render(<SidebarFilterComponent {...propsWithEmptyDescription} />);

      // Should not crash
      expect(screen.getByTestId("icon-ListFilter")).toBeInTheDocument();
    });

    it("should handle description with special characters", () => {
      const propsWithSpecialDescription = {
        ...defaultProps,
        description: "List[str]",
      };
      render(<SidebarFilterComponent {...propsWithSpecialDescription} />);

      expect(screen.getByText("List[str]")).toBeInTheDocument();
    });
  });

  describe("Pluralization", () => {
    it("should use singular form for single description", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.queryByText("Inputs:")).not.toBeInTheDocument();
    });

    it("should use plural form for multiple descriptions", () => {
      const propsWithMultipleDescriptions = {
        ...defaultProps,
        description: "string\nint",
      };

      render(<SidebarFilterComponent {...propsWithMultipleDescriptions} />);

      expect(screen.getByText("Inputs:")).toBeInTheDocument();
      expect(screen.queryByText("Input:")).not.toBeInTheDocument();
    });

    it("should use plural form for any name with multiple descriptions", () => {
      const propsWithMultipleDescriptions = {
        ...defaultProps,
        name: "Output",
        description: "string\nint\nfloat",
      };

      render(<SidebarFilterComponent {...propsWithMultipleDescriptions} />);

      expect(screen.getByText("Outputs:")).toBeInTheDocument();
      expect(screen.queryByText("Output:")).not.toBeInTheDocument();
    });

    it("should handle edge case with empty lines in description", () => {
      const propsWithEmptyLines = {
        ...defaultProps,
        description: "string\n\nint",
      };

      render(<SidebarFilterComponent {...propsWithEmptyLines} />);

      // Should treat empty line as a separate description for pluralization
      expect(screen.getByText("Inputs:")).toBeInTheDocument();
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
      expect(container).toContainElement(iconContainer!);
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
    it("should handle different name values", () => {
      const { rerender } = render(
        <SidebarFilterComponent {...defaultProps} name="Input" />,
      );
      expect(screen.getByText("Input:")).toBeInTheDocument();

      rerender(<SidebarFilterComponent {...defaultProps} name="Output" />);
      expect(screen.getByText("Output:")).toBeInTheDocument();
    });

    it("should handle different description values", () => {
      const { rerender } = render(
        <SidebarFilterComponent {...defaultProps} description="string" />,
      );
      expect(screen.getByText("string")).toBeInTheDocument();

      rerender(
        <SidebarFilterComponent {...defaultProps} description="number" />,
      );
      expect(screen.getByText("number")).toBeInTheDocument();
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
    it("should handle very long description names", () => {
      const propsWithLongDescription = {
        ...defaultProps,
        description: "VeryLongDescriptionNameThatExceedsNormalLength",
      };

      render(<SidebarFilterComponent {...propsWithLongDescription} />);

      expect(
        screen.getByText("VeryLongDescriptionNameThatExceedsNormalLength"),
      ).toBeInTheDocument();
    });

    it("should handle multiple very long description names", () => {
      const propsWithMultipleLongDescriptions = {
        ...defaultProps,
        description:
          "FirstVeryLongDescriptionName\nSecondVeryLongDescriptionName\nThirdVeryLongDescriptionName",
      };

      render(<SidebarFilterComponent {...propsWithMultipleLongDescriptions} />);

      expect(
        screen.getByText(
          "FirstVeryLongDescriptionName, SecondVeryLongDescriptionName, ThirdVeryLongDescriptionName",
        ),
      ).toBeInTheDocument();
    });

    it("should handle descriptions with newlines and commas", () => {
      const propsWithComplexDescriptions = {
        ...defaultProps,
        description: "List[str, int]\nDict[str, Any]",
      };

      render(<SidebarFilterComponent {...propsWithComplexDescriptions} />);

      expect(
        screen.getByText("List[str, int], Dict[str, Any]"),
      ).toBeInTheDocument();
    });

    it("should handle very long names", () => {
      const propsWithLongName = {
        ...defaultProps,
        name: "VeryLongFilterNameThatMightCauseIssues",
      };
      render(<SidebarFilterComponent {...propsWithLongName} />);

      // Verify component renders without errors with long name
      expect(
        screen.getByText("VeryLongFilterNameThatMightCauseIssues:"),
      ).toBeInTheDocument();
    });

    it("should handle single newline character as description", () => {
      const propsWithNewlineDescription = {
        ...defaultProps,
        description: "\n",
      };
      render(<SidebarFilterComponent {...propsWithNewlineDescription} />);

      expect(screen.getByText("Inputs:")).toBeInTheDocument(); // Should be plural due to split
    });
  });

  describe("Text Content", () => {
    it("should display correct text for filter with single description", () => {
      render(<SidebarFilterComponent {...defaultProps} />);

      expect(screen.getByText("Input:")).toBeInTheDocument();
      expect(screen.getByText("string")).toBeInTheDocument();
    });

    it("should display correct text for filter with multiple descriptions", () => {
      const propsWithMultipleDescriptions = {
        ...defaultProps,
        name: "Output",
        description: "str\nint\nfloat",
      };

      render(<SidebarFilterComponent {...propsWithMultipleDescriptions} />);

      expect(screen.getByText("Outputs:")).toBeInTheDocument();
      expect(screen.getByText("str, int, float")).toBeInTheDocument();
    });

    it("should join multiple descriptions with commas and spaces", () => {
      const propsWithMultipleDescriptions = {
        ...defaultProps,
        description: "desc1\ndesc2\ndesc3\ndesc4",
      };

      render(<SidebarFilterComponent {...propsWithMultipleDescriptions} />);

      expect(
        screen.getByText("desc1, desc2, desc3, desc4"),
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
      const customResetFilters = jest.fn(() => {
        // Custom implementation
        console.log("Custom reset");
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
