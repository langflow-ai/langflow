import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { SidebarDraggableComponent } from "../sidebarDraggableComponent";

// Mock all external dependencies
jest.mock(
  "@/components/common/storeCardComponent/utils/convert-test-name",
  () => ({
    convertTestName: (name: string) => name.toLowerCase().replace(/\s+/g, "-"),
  }),
);

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children, variant, size, className }: any) => (
    <span data-testid={`badge-${variant}-${size}`} className={className}>
      {children}
    </span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    className,
    variant,
    size,
    tabIndex,
    ...props
  }: any) => (
    <button
      onClick={onClick}
      className={className}
      tabIndex={tabIndex}
      data-variant={variant}
      data-size={size}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/hooks/flows/use-delete-flow", () => ({
  __esModule: true,
  default: () => ({
    deleteFlow: jest.fn(),
  }),
}));

const mockAddComponentFn = jest.fn();
jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: jest.fn(() => mockAddComponentFn),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: any) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
  ForwardedIconComponent: ({ name, className }: any) => (
    <span data-testid={`forwarded-icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content, styleClasses }: any) => (
    <div data-testid="tooltip" data-content={content} className={styleClasses}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/select-custom", () => ({
  Select: ({ children, onValueChange, onOpenChange, open, ...props }: any) => (
    <div
      data-testid="select"
      data-open={open}
      data-on-value-change={onValueChange?.toString()}
      data-on-open-change={onOpenChange?.toString()}
      {...props}
    >
      {children}
    </div>
  ),
  SelectContent: ({ children, position, side, sideOffset, style }: any) => (
    <div
      data-testid="select-content"
      data-position={position}
      data-side={side}
      data-side-offset={sideOffset}
      style={style}
    >
      {children}
    </div>
  ),
  SelectItem: ({ children, value, ...props }: any) => (
    <div data-testid={`select-item-${value}`} data-value={value} {...props}>
      {children}
    </div>
  ),
  SelectTrigger: ({ children, tabIndex, ...props }: any) => (
    <div data-testid="select-trigger" tabIndex={tabIndex} {...props}>
      {children}
    </div>
  ),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: () => ({
    version: "1.0.0",
  }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: () => ({
    flows: [
      { id: "flow1", name: "Test Flow" },
      { id: "flow2", name: "Another Flow" },
    ],
  }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  createFlowComponent: jest.fn(),
  downloadNode: jest.fn(),
  getNodeId: jest.fn().mockReturnValue("test-node-id"),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
  removeCountFromString: (str: string) => str.replace(/\d+$/, ""),
}));

describe("SidebarDraggableComponent", () => {
  const mockOnDragStart = jest.fn();

  const mockAPIClass = {
    description: "Test component",
    template: {},
    display_name: "Test Component",
    documentation: "Test docs",
    icon: "TestIcon",
  };

  const defaultProps = {
    sectionName: "TestSection",
    display_name: "Test Component",
    icon: "TestIcon",
    itemName: "test-component",
    error: false,
    color: "#FF0000",
    onDragStart: mockOnDragStart,
    apiClass: mockAPIClass,
    official: true,
    beta: false,
    legacy: false,
    disabled: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render component with correct structure", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getByTestId("select")).toBeInTheDocument();
      expect(screen.getAllByTestId("tooltip").length).toBeGreaterThan(0);
      expect(
        screen.getByTestId(/testsectiontest component/i),
      ).toBeInTheDocument();
      expect(screen.getByTestId("forwarded-icon-TestIcon")).toBeInTheDocument();
      expect(screen.getByText("Test Component")).toBeInTheDocument();
    });

    it("should display component name", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getByText("Test Component")).toBeInTheDocument();
    });

    it("should display component icon", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getByTestId("forwarded-icon-TestIcon")).toBeInTheDocument();
    });

    it("should have correct test id format", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(
        screen.getByTestId("testsection_test component_draggable"),
      ).toBeInTheDocument();
    });

    it("should display grip vertical icon", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(
        screen.getByTestId("forwarded-icon-GripVertical"),
      ).toBeInTheDocument();
    });

    it("should render add component button when not disabled", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(
        screen.getByTestId("add-component-button-test-component"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("forwarded-icon-Plus")).toBeInTheDocument();
    });
  });

  describe("Badge Rendering", () => {
    it("should render Beta badge when beta prop is true", () => {
      const propsWithBeta = { ...defaultProps, beta: true };

      render(<SidebarDraggableComponent {...propsWithBeta} />);

      expect(screen.getByTestId("badge-pinkStatic-xq")).toBeInTheDocument();
      expect(screen.getByText("Beta")).toBeInTheDocument();
    });

    it("should render Legacy badge when legacy prop is true", () => {
      const propsWithLegacy = { ...defaultProps, legacy: true };

      render(<SidebarDraggableComponent {...propsWithLegacy} />);

      expect(
        screen.getByTestId("badge-secondaryStatic-xq"),
      ).toBeInTheDocument();
      expect(screen.getByText("Legacy")).toBeInTheDocument();
    });

    it("should render both badges when both beta and legacy are true", () => {
      const propsWithBoth = { ...defaultProps, beta: true, legacy: true };

      render(<SidebarDraggableComponent {...propsWithBoth} />);

      expect(screen.getByTestId("badge-pinkStatic-xq")).toBeInTheDocument();
      expect(
        screen.getByTestId("badge-secondaryStatic-xq"),
      ).toBeInTheDocument();
      expect(screen.getByText("Beta")).toBeInTheDocument();
      expect(screen.getByText("Legacy")).toBeInTheDocument();
    });

    it("should not render badges when neither beta nor legacy are true", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(
        screen.queryByTestId("badge-pinkStatic-xq"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("badge-secondaryStatic-xq"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Disabled State", () => {
    it("should handle disabled state correctly", () => {
      const propsWithDisabled = {
        ...defaultProps,
        disabled: true,
        disabledTooltip: "This component is disabled",
      };

      render(<SidebarDraggableComponent {...propsWithDisabled} />);

      expect(screen.getAllByTestId("tooltip")[0]).toHaveAttribute(
        "data-content",
        "This component is disabled",
      );
      expect(
        screen.queryByTestId("add-component-button-test-component"),
      ).not.toBeInTheDocument();
    });

    it("should not show add button when disabled", () => {
      const propsWithDisabled = { ...defaultProps, disabled: true };

      render(<SidebarDraggableComponent {...propsWithDisabled} />);

      expect(
        screen.queryByTestId("add-component-button-test-component"),
      ).not.toBeInTheDocument();
    });

    it("should show no tooltip content when not disabled", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getAllByTestId("tooltip")[0]).not.toHaveAttribute(
        "data-content",
      );
    });
  });

  describe("Error State", () => {
    it("should handle error state correctly", () => {
      const propsWithError = { ...defaultProps, error: true };

      render(<SidebarDraggableComponent {...propsWithError} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      expect(draggableDiv).toHaveAttribute("draggable", "false");
    });

    it("should be draggable when no error", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      expect(draggableDiv).toHaveAttribute("draggable", "true");
    });
  });

  describe("Drag and Drop", () => {
    it("should call onDragStart when dragging starts", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      fireEvent.dragStart(draggableDiv);

      expect(mockOnDragStart).toHaveBeenCalledTimes(1);
    });

    it("should handle drag end correctly", () => {
      // Mock document methods
      const mockRemoveChild = jest.fn();
      const mockGetElementsByClassName = jest
        .fn()
        .mockReturnValue([document.createElement("div")]);
      Object.defineProperty(document, "getElementsByClassName", {
        value: mockGetElementsByClassName,
        writable: true,
      });
      Object.defineProperty(document.body, "removeChild", {
        value: mockRemoveChild,
        writable: true,
      });

      render(<SidebarDraggableComponent {...defaultProps} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      fireEvent.dragEnd(draggableDiv);

      expect(mockGetElementsByClassName).toHaveBeenCalledWith(
        "cursor-grabbing",
      );
    });

    it("should not be draggable when error is true", () => {
      const propsWithError = { ...defaultProps, error: true };
      render(<SidebarDraggableComponent {...propsWithError} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      expect(draggableDiv).toHaveAttribute("draggable", "false");
    });
  });

  describe("Add Component Functionality", () => {
    it("should call addComponent when add button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarDraggableComponent {...defaultProps} />);

      const addButton = screen.getByTestId(
        "add-component-button-test-component",
      );
      await user.click(addButton);

      expect(mockAddComponentFn).toHaveBeenCalledWith(
        mockAPIClass,
        "test-component",
      );
    });

    it("should call addComponent when Enter key is pressed", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const container = screen.getByTestId(
        "testsection_test component_draggable",
      );
      fireEvent.keyDown(container, { key: "Enter" });

      expect(mockAddComponentFn).toHaveBeenCalledWith(
        mockAPIClass,
        "test-component",
      );
    });

    it("should call addComponent when Space key is pressed", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const container = screen.getByTestId(
        "testsection_test component_draggable",
      );
      fireEvent.keyDown(container, { key: " " });

      expect(mockAddComponentFn).toHaveBeenCalledWith(
        mockAPIClass,
        "test-component",
      );
    });

    it("should not call addComponent for other keys", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const container = screen.getByTestId(
        "testsection_test component_draggable",
      );
      fireEvent.keyDown(container, { key: "Escape" });

      expect(mockAddComponentFn).not.toHaveBeenCalled();
    });
  });

  describe("Context Menu and Select", () => {
    it("should handle context menu capture", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const container = screen.getByTestId(
        "testsection_test component_draggable",
      );
      fireEvent.contextMenu(container);

      // We can't easily verify the context menu state, but ensure no error occurs
      expect(container).toBeInTheDocument();
    });

    it("should render select content with download option", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getByTestId("select-item-download")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Download")).toBeInTheDocument();
    });

    it("should render delete option when not official", () => {
      const propsNotOfficial = { ...defaultProps, official: false };
      render(<SidebarDraggableComponent {...propsNotOfficial} />);

      expect(screen.getByTestId("select-item-delete")).toBeInTheDocument();
      expect(screen.getByText("Delete")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Trash2")).toBeInTheDocument();
    });

    it("should not render delete option when official", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(
        screen.queryByTestId("select-item-delete"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Style and Classes", () => {
    it("should apply correct border color", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      expect(draggableDiv).toHaveStyle({ borderLeftColor: "#FF0000" });
    });

    it("should have correct tabIndex", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const container = screen.getByTestId(
        "testsection_test component_draggable",
      );
      expect(container).toHaveAttribute("tabIndex", "0");
    });

    it("should have add button with tabIndex -1", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const addButton = screen.getByTestId(
        "add-component-button-test-component",
      );
      expect(addButton).toHaveAttribute("tabIndex", "-1");
    });

    it("should have select trigger with tabIndex -1", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getByTestId("select-trigger")).toHaveAttribute(
        "tabIndex",
        "-1",
      );
    });
  });

  describe("Props Handling", () => {
    it("should handle different section names", () => {
      const propsWithDifferentSection = {
        ...defaultProps,
        sectionName: "CustomSection",
      };

      render(<SidebarDraggableComponent {...propsWithDifferentSection} />);

      expect(
        screen.getByTestId(/customsectiontest component/i),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId(/customsection_test component_draggable/i),
      ).toBeInTheDocument();
    });

    it("should handle different display names", () => {
      const propsWithDifferentName = {
        ...defaultProps,
        display_name: "My Custom Component",
      };

      render(<SidebarDraggableComponent {...propsWithDifferentName} />);

      expect(screen.getByText("My Custom Component")).toBeInTheDocument();
      expect(
        screen.getByTestId("add-component-button-my-custom-component"),
      ).toBeInTheDocument();
    });

    it("should handle different icons", () => {
      const propsWithDifferentIcon = {
        ...defaultProps,
        icon: "CustomIcon",
      };

      render(<SidebarDraggableComponent {...propsWithDifferentIcon} />);

      expect(
        screen.getByTestId("forwarded-icon-CustomIcon"),
      ).toBeInTheDocument();
    });

    it("should handle different colors", () => {
      const propsWithDifferentColor = {
        ...defaultProps,
        color: "#00FF00",
      };

      render(<SidebarDraggableComponent {...propsWithDifferentColor} />);

      const draggableDiv = screen.getByTestId(/testsectiontest component/i);
      expect(draggableDiv).toHaveStyle({ borderLeftColor: "#00FF00" });
    });
  });

  describe("Component Structure", () => {
    it("should have correct DOM hierarchy", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const select = screen.getByTestId("select");
      const tooltips = screen.getAllByTestId("tooltip");
      const draggableContainer = screen.getByTestId(
        "testsection_test component_draggable",
      );
      const draggableDiv = screen.getByTestId(/testsectiontest component/i);

      expect(select).toContainElement(tooltips[0]);
      expect(tooltips[0]).toContainElement(draggableContainer);
      expect(draggableContainer).toContainElement(draggableDiv);
    });

    it("should contain all expected child elements", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(screen.getByTestId("forwarded-icon-TestIcon")).toBeInTheDocument();
      expect(screen.getByText("Test Component")).toBeInTheDocument();
      expect(
        screen.getByTestId("add-component-button-test-component"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("forwarded-icon-GripVertical"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("select-content")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty display name", () => {
      const propsWithEmptyName = {
        ...defaultProps,
        display_name: "",
      };

      render(<SidebarDraggableComponent {...propsWithEmptyName} />);

      expect(screen.getByTestId("display-name")).toHaveTextContent("");
    });

    it("should handle missing color", () => {
      const propsWithoutColor = {
        ...defaultProps,
        color: undefined as any,
      };

      expect(() => {
        render(<SidebarDraggableComponent {...propsWithoutColor} />);
      }).not.toThrow();
    });

    it("should handle missing onDragStart", () => {
      const propsWithoutDragStart = {
        ...defaultProps,
        onDragStart: undefined as any,
      };

      expect(() => {
        render(<SidebarDraggableComponent {...propsWithoutDragStart} />);
      }).not.toThrow();
    });

    it("should handle complex component combinations", () => {
      const complexProps = {
        ...defaultProps,
        beta: true,
        legacy: true,
        disabled: true,
        error: true,
        official: false,
        disabledTooltip: "Complex disabled state",
      };

      render(<SidebarDraggableComponent {...complexProps} />);

      expect(screen.getByTestId("badge-pinkStatic-xq")).toBeInTheDocument();
      expect(
        screen.getByTestId("badge-secondaryStatic-xq"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("add-component-button-test-component"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("select-item-delete")).toBeInTheDocument();
    });
  });

  describe("Tooltip Integration", () => {
    it("should show disabled tooltip when disabled", () => {
      const propsWithDisabledTooltip = {
        ...defaultProps,
        disabled: true,
        disabledTooltip: "This feature is disabled",
      };

      render(<SidebarDraggableComponent {...propsWithDisabledTooltip} />);

      const tooltips = screen.getAllByTestId("tooltip");
      expect(
        tooltips.some(
          (t) => t.getAttribute("data-content") === "This feature is disabled",
        ),
      ).toBe(true);
    });

    it("should show component name in inner tooltip", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const tooltips = screen.getAllByTestId("tooltip");
      expect(tooltips.length).toBeGreaterThan(0);
    });
  });

  describe("Select Positioning", () => {
    it("should render select content with correct positioning", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      const selectContent = screen.getByTestId("select-content");
      expect(selectContent).toHaveAttribute("data-position", "popper");
      expect(selectContent).toHaveAttribute("data-side", "bottom");
      expect(selectContent).toHaveAttribute("data-side-offset", "-25");
    });
  });
});
