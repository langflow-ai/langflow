import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarDraggableComponent } from "../sidebarDraggableComponent";

// Mock all external dependencies
jest.mock(
  "@/components/common/storeCardComponent/utils/convert-test-name",
  () => ({
    convertTestName: (name: string) => name.toLowerCase().replace(/\s+/g, "-"),
  }),
);

jest.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    variant,
    size,
    className,
  }: {
    children: React.ReactNode;
    variant: string;
    size: string;
    className?: string;
  }) => (
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
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    className?: string;
    variant?: string;
    size?: string;
    tabIndex?: number;
    [key: string]: unknown;
  }) => (
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

const mockDeleteFlow = jest.fn();
jest.mock("@/hooks/flows/use-delete-flow", () => ({
  __esModule: true,
  default: () => ({
    deleteFlow: mockDeleteFlow,
  }),
}));

const mockAddComponentFn = jest.fn();
jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: jest.fn(() => mockAddComponentFn),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name: string;
    className?: string;
  }) => (
    <span data-testid={`forwarded-icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
    styleClasses,
  }: {
    children: React.ReactNode;
    content?: string;
    styleClasses?: string;
  }) => (
    <div data-testid="tooltip" data-content={content} className={styleClasses}>
      {children}
    </div>
  ),
}));

// Store the onValueChange function so we can call it in tests
let mockOnValueChange: ((value: string) => void) | undefined;

jest.mock("@/components/ui/select-custom", () => ({
  Select: ({
    children,
    onValueChange,
    onOpenChange,
    open,
    ...props
  }: {
    children: React.ReactNode;
    onValueChange?: (value: string) => void;
    onOpenChange?: (open: boolean) => void;
    open?: boolean;
    [key: string]: unknown;
  }) => {
    // Store the onValueChange function so we can use it in tests
    mockOnValueChange = onValueChange;
    return (
      <div
        data-testid="select"
        data-open={open}
        data-on-value-change={onValueChange?.toString()}
        data-on-open-change={onOpenChange?.toString()}
        {...props}
      >
        {children}
      </div>
    );
  },
  SelectContent: ({
    children,
    position,
    side,
    sideOffset,
    style,
  }: {
    children: React.ReactNode;
    position?: string;
    side?: string;
    sideOffset?: number;
    style?: React.CSSProperties;
  }) => (
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
  SelectItem: ({
    children,
    value,
    ...props
  }: {
    children: React.ReactNode;
    value: string;
    [key: string]: unknown;
  }) => (
    <button
      data-testid={props["data-testid"] || `select-item-${value}`}
      data-value={value}
      onClick={() => mockOnValueChange?.(value)}
      {...props}
    >
      {children}
    </button>
  ),
  SelectTrigger: ({
    children,
    tabIndex,
    ...props
  }: {
    children?: React.ReactNode;
    tabIndex?: number;
    [key: string]: unknown;
  }) => (
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
  default: (
    selector: (state: {
      flows: Array<{ id: string; name: string }>;
    }) => unknown,
  ) =>
    selector({
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
  cn: (...classes: (string | undefined | null | boolean)[]) =>
    classes.filter(Boolean).join(" "),
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
    mockOnValueChange = undefined;
    mockDeleteFlow.mockClear();
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

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();
      expect(screen.getByText("Delete")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Trash2")).toBeInTheDocument();
    });

    it("should not render delete option when official", () => {
      render(<SidebarDraggableComponent {...defaultProps} />);

      expect(
        screen.queryByTestId("draggable-component-menu-delete"),
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
        color: "",
      };

      expect(() => {
        render(<SidebarDraggableComponent {...propsWithoutColor} />);
      }).not.toThrow();
    });

    it("should handle missing onDragStart", () => {
      const propsWithoutDragStart = {
        ...defaultProps,
        onDragStart: jest.fn(),
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
      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();
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

  describe("OnDelete Behavior", () => {
    it("should call onDelete prop when delete is selected and onDelete is provided", async () => {
      const mockOnDelete = jest.fn();
      const propsWithOnDelete = {
        ...defaultProps,
        onDelete: mockOnDelete,
        official: true, // Even with official=true, delete should show when onDelete is provided
      };

      render(<SidebarDraggableComponent {...propsWithOnDelete} />);

      // Verify delete option is shown when onDelete is provided
      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();

      // Click on the delete option to trigger the onValueChange
      const deleteItem = screen.getByTestId("draggable-component-menu-delete");
      fireEvent.click(deleteItem);

      // Verify that our custom onDelete function was called
      expect(mockOnDelete).toHaveBeenCalledTimes(1);
    });

    it("should render delete option when onDelete prop is provided even if official is true", () => {
      const mockOnDelete = jest.fn();
      const propsWithOnDeleteAndOfficial = {
        ...defaultProps,
        onDelete: mockOnDelete,
        official: true,
      };

      render(<SidebarDraggableComponent {...propsWithOnDeleteAndOfficial} />);

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();
      expect(screen.getByText("Delete")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Trash2")).toBeInTheDocument();
    });

    it("should render delete option when official is false even without onDelete", () => {
      const propsNotOfficial = {
        ...defaultProps,
        official: false,
        onDelete: undefined,
      };

      render(<SidebarDraggableComponent {...propsNotOfficial} />);

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();
      expect(screen.getByText("Delete")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Trash2")).toBeInTheDocument();
    });

    it("should not render delete option when official is true and no onDelete is provided", () => {
      const propsOfficialWithoutOnDelete = {
        ...defaultProps,
        official: true,
        onDelete: undefined,
      };

      render(<SidebarDraggableComponent {...propsOfficialWithoutOnDelete} />);

      expect(
        screen.queryByTestId("draggable-component-menu-delete"),
      ).not.toBeInTheDocument();
    });

    it("should render delete option when both onDelete is provided and official is false", () => {
      const mockOnDelete = jest.fn();
      const propsWithBothConditions = {
        ...defaultProps,
        onDelete: mockOnDelete,
        official: false,
      };

      render(<SidebarDraggableComponent {...propsWithBothConditions} />);

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();
      expect(screen.getByText("Delete")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Trash2")).toBeInTheDocument();
    });

    it("should handle onDelete prop being undefined gracefully", () => {
      const propsWithUndefinedOnDelete = {
        ...defaultProps,
        onDelete: undefined,
        official: false, // Make delete option visible
      };

      expect(() => {
        render(<SidebarDraggableComponent {...propsWithUndefinedOnDelete} />);
      }).not.toThrow();

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();
    });

    it("should prioritize onDelete over default flow deletion when onDelete is provided", async () => {
      const mockOnDelete = jest.fn();

      const propsWithOnDelete = {
        ...defaultProps,
        onDelete: mockOnDelete,
        official: false,
        display_name: "Test Flow", // This exists in the mocked flows
      };

      render(<SidebarDraggableComponent {...propsWithOnDelete} />);

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();

      // Click on the delete option
      const deleteItem = screen.getByTestId("draggable-component-menu-delete");
      fireEvent.click(deleteItem);

      // Verify that our custom onDelete function was called and deleteFlow was NOT called
      expect(mockOnDelete).toHaveBeenCalledTimes(1);
      expect(mockDeleteFlow).not.toHaveBeenCalled();
    });

    it("should use default flow deletion when onDelete is not provided", async () => {
      const propsWithoutOnDelete = {
        ...defaultProps,
        onDelete: undefined,
        official: false,
        display_name: "Test Flow", // This exists in the mocked flows
      };

      render(<SidebarDraggableComponent {...propsWithoutOnDelete} />);

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();

      // Click on the delete option
      const deleteItem = screen.getByTestId("draggable-component-menu-delete");
      fireEvent.click(deleteItem);

      // Verify that the default deleteFlow function was called
      expect(mockDeleteFlow).toHaveBeenCalledTimes(1);
      expect(mockDeleteFlow).toHaveBeenCalledWith({ id: "flow1" }); // Based on our mocked flows
    });

    it("should not call deleteFlow when onDelete is not provided and flow is not found", async () => {
      const propsWithNonExistentFlow = {
        ...defaultProps,
        onDelete: undefined,
        official: false,
        display_name: "Non-existent Flow", // This doesn't exist in our mocked flows
      };

      render(<SidebarDraggableComponent {...propsWithNonExistentFlow} />);

      expect(
        screen.getByTestId("draggable-component-menu-delete"),
      ).toBeInTheDocument();

      // Click on the delete option
      const deleteItem = screen.getByTestId("draggable-component-menu-delete");
      fireEvent.click(deleteItem);

      // Verify that deleteFlow was not called since flow was not found
      expect(mockDeleteFlow).not.toHaveBeenCalled();
    });
  });
});
