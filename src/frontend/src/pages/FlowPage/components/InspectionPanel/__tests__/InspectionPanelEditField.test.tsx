import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InspectionPanelEditField from "../components/InspectionPanelEditField";
import type { NodeDataType } from "@/types/flow";

// Mock IconComponent
jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIconComponent({ name, className }: any) {
    return (
      <span data-testid={`icon-${name}`} className={className}>
        {name}
      </span>
    );
  };
});

// Mock useHandleOnNewValue hook
const mockHandleOnNewValue = jest.fn();
jest.mock("@/CustomNodes/hooks/use-handle-new-value", () => ({
  __esModule: true,
  default: () => ({
    handleOnNewValue: mockHandleOnNewValue,
  }),
}));

// Mock utils
jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("InspectionPanelEditField", () => {
  const createMockData = (overrides = {}): NodeDataType => ({
    id: "test-node-123",
    type: "TestComponent",
    node: {
      display_name: "Test Node",
      description: "Test description",
      template: {
        test_field: {
          type: "str",
          value: "test value",
          advanced: false,
          show: true,
        },
      },
      ...overrides,
    },
  });

  const defaultProps = {
    data: createMockData(),
    name: "test_field",
    title: "Test Field",
    description: "This is a test field",
    isOnCanvas: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render field title", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      expect(screen.getByText("Test Field")).toBeInTheDocument();
    });

    it("should render field description", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      expect(screen.getByText("This is a test field")).toBeInTheDocument();
    });

    it("should not render description when empty", () => {
      const props = { ...defaultProps, description: "" };
      render(<InspectionPanelEditField {...props} />);

      expect(
        screen.queryByText("This is a test field"),
      ).not.toBeInTheDocument();
    });

    it("should render toggle button", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button).toBeInTheDocument();
    });

    it("should have correct test id on button", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      expect(screen.getByTestId("showtest_field")).toBeInTheDocument();
    });
  });

  describe("Icon Display", () => {
    it("should show Plus icon when field is not on canvas", () => {
      const props = { ...defaultProps, isOnCanvas: false };
      render(<InspectionPanelEditField {...props} />);

      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
      expect(screen.queryByTestId("icon-Minus")).not.toBeInTheDocument();
    });

    it("should show Minus icon when field is on canvas", () => {
      const props = { ...defaultProps, isOnCanvas: true };
      render(<InspectionPanelEditField {...props} />);

      expect(screen.getByTestId("icon-Minus")).toBeInTheDocument();
      expect(screen.queryByTestId("icon-Plus")).not.toBeInTheDocument();
    });
  });

  describe("Button Styling", () => {
    it("should apply primary styling when field is on canvas", () => {
      const props = { ...defaultProps, isOnCanvas: true };
      render(<InspectionPanelEditField {...props} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button).toHaveClass("bg-primary/10");
      expect(button).toHaveClass("text-primary");
    });

    it("should apply muted styling when field is not on canvas", () => {
      const props = { ...defaultProps, isOnCanvas: false };
      render(<InspectionPanelEditField {...props} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button).toHaveClass("bg-muted");
      expect(button).toHaveClass("text-muted-foreground");
    });

    it("should have hover classes", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button.className).toContain("hover:");
    });
  });

  describe("Accessibility", () => {
    it("should have role checkbox", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button).toHaveAttribute("role", "checkbox");
    });

    it("should have aria-checked false when not on canvas", () => {
      const props = { ...defaultProps, isOnCanvas: false };
      render(<InspectionPanelEditField {...props} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button).toHaveAttribute("aria-checked", "false");
    });

    it("should have aria-checked true when on canvas", () => {
      const props = { ...defaultProps, isOnCanvas: true };
      render(<InspectionPanelEditField {...props} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      expect(button).toHaveAttribute("aria-checked", "true");
    });
  });

  describe("Toggle Functionality", () => {
    it("should call handleOnNewValue when button is clicked (not on canvas)", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, isOnCanvas: false };
      render(<InspectionPanelEditField {...props} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      await user.click(button);

      expect(mockHandleOnNewValue).toHaveBeenCalledTimes(1);
      expect(mockHandleOnNewValue).toHaveBeenCalledWith({ advanced: false });
    });

    it("should call handleOnNewValue when button is clicked (on canvas)", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, isOnCanvas: true };
      render(<InspectionPanelEditField {...props} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);
      await user.click(button);

      expect(mockHandleOnNewValue).toHaveBeenCalledTimes(1);
      expect(mockHandleOnNewValue).toHaveBeenCalledWith({ advanced: true });
    });

    it("should handle multiple clicks", async () => {
      const user = userEvent.setup();
      render(<InspectionPanelEditField {...defaultProps} />);

      const button = screen.getByTestId(`show${defaultProps.name}`);

      await user.click(button);
      await user.click(button);
      await user.click(button);

      expect(mockHandleOnNewValue).toHaveBeenCalledTimes(3);
    });
  });

  describe("Text Truncation", () => {
    it("should apply truncate class to title", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      const title = screen.getByText("Test Field");
      expect(title).toHaveClass("truncate");
    });

    it("should apply truncate class to description", () => {
      render(<InspectionPanelEditField {...defaultProps} />);

      const description = screen.getByText("This is a test field");
      expect(description).toHaveClass("truncate");
    });

    it("should handle very long titles", () => {
      const props = {
        ...defaultProps,
        title: "This is a very long title that should be truncated properly",
      };
      render(<InspectionPanelEditField {...props} />);

      expect(
        screen.getByText(
          "This is a very long title that should be truncated properly",
        ),
      ).toBeInTheDocument();
    });

    it("should handle very long descriptions", () => {
      const props = {
        ...defaultProps,
        description:
          "This is a very long description that should be truncated properly to avoid layout issues",
      };
      render(<InspectionPanelEditField {...props} />);

      expect(
        screen.getByText(
          "This is a very long description that should be truncated properly to avoid layout issues",
        ),
      ).toBeInTheDocument();
    });
  });

  describe("Different Field Names", () => {
    it("should handle field names with underscores", () => {
      const props = { ...defaultProps, name: "my_custom_field" };
      render(<InspectionPanelEditField {...props} />);

      expect(screen.getByTestId("showmy_custom_field")).toBeInTheDocument();
    });

    it("should handle field names with numbers", () => {
      const props = { ...defaultProps, name: "field123" };
      render(<InspectionPanelEditField {...props} />);

      expect(screen.getByTestId("showfield123")).toBeInTheDocument();
    });

    it("should handle camelCase field names", () => {
      const props = { ...defaultProps, name: "myCustomField" };
      render(<InspectionPanelEditField {...props} />);

      expect(screen.getByTestId("showmyCustomField")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty title", () => {
      const props = { ...defaultProps, title: "" };
      render(<InspectionPanelEditField {...props} />);

      // Component should still render
      expect(
        screen.getByTestId(`show${defaultProps.name}`),
      ).toBeInTheDocument();
    });

    it("should handle special characters in description", () => {
      const props = {
        ...defaultProps,
        description: "Description with <special> & characters",
      };
      render(<InspectionPanelEditField {...props} />);

      expect(
        screen.getByText("Description with <special> & characters"),
      ).toBeInTheDocument();
    });

    it("should handle null description gracefully", () => {
      const props = { ...defaultProps, description: null as any };

      expect(() => {
        render(<InspectionPanelEditField {...props} />);
      }).not.toThrow();
    });
  });

  describe("Layout", () => {
    it("should have correct container classes", () => {
      const { container } = render(
        <InspectionPanelEditField {...defaultProps} />,
      );

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass("group");
      expect(wrapper).toHaveClass("flex");
      expect(wrapper).toHaveClass("items-center");
      expect(wrapper).toHaveClass("justify-between");
    });

    it("should have hover effect class", () => {
      const { container } = render(
        <InspectionPanelEditField {...defaultProps} />,
      );

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.className).toContain("hover:");
    });
  });
});
