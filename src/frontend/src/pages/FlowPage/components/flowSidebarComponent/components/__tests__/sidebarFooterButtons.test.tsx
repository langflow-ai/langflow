import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SidebarMenuButtons from "../sidebarFooterButtons";

// Mock the UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    className,
    disabled,
    unstyled,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    className?: string;
    disabled?: boolean;
    unstyled?: boolean;
    [key: string]: unknown;
  }) => (
    <button
      type="button"
      onClick={onClick}
      className={className}
      disabled={disabled}
      data-unstyled={unstyled}
      {...props}
    >
      {children}
    </button>
  ),
}));

// Mock sidebar hook with default values
const mockUseSidebar = jest.fn();

jest.mock("@/components/ui/sidebar", () => ({
  SidebarMenuButton: ({
    children,
    asChild,
    className,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
    className?: string;
  }) => (
    <div
      data-testid="sidebar-menu-button"
      data-as-child={asChild}
      className={className}
    >
      {children}
    </div>
  ),
  useSidebar: () => mockUseSidebar(),
}));

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: true,
}));

// Mock navigation hook
const mockNavigate = jest.fn();
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

// Mock modal component
jest.mock("@/modals/addMcpServerModal", () => ({
  __esModule: true,
  default: ({
    open,
    setOpen,
  }: {
    open: boolean;
    setOpen: (open: boolean) => void;
  }) => (
    <div data-testid="add-mcp-server-modal" data-open={open}>
      <button type="button" onClick={() => setOpen(false)}>
        Close Modal
      </button>
    </div>
  ),
}));

describe("SidebarMenuButtons", () => {
  const mockAddComponent = jest.fn();
  const mockCustomComponent = {
    description: "Custom test component",
    template: {},
    display_name: "Custom Component",
    documentation: "Custom docs",
  };

  const defaultProps = {
    customComponent: mockCustomComponent,
    addComponent: mockAddComponent,
    isLoading: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockNavigate.mockClear();
    // Reset to default sidebar state
    mockUseSidebar.mockReturnValue({
      activeSection: "components",
    });
  });

  describe("Basic Rendering - Custom Component Mode", () => {
    it("should render custom component button when not in MCP section", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
      expect(screen.getByText("New Custom Component")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    });

    it("should render custom component button container", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
    });

    it("should display correct text for custom component button", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByText("New Custom Component")).toBeInTheDocument();
    });

    it("should display Plus icon", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    });
  });

  describe("Custom Component Button Functionality", () => {
    it("should call addComponent when custom component button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(mockAddComponent).toHaveBeenCalledWith(
        mockCustomComponent,
        "CustomComponent",
      );
      expect(mockAddComponent).toHaveBeenCalledTimes(1);
    });

    it("should not call addComponent when customComponent is undefined", async () => {
      const user = userEvent.setup();
      const propsWithoutCustomComponent = {
        ...defaultProps,
        customComponent: undefined,
      };

      render(<SidebarMenuButtons {...propsWithoutCustomComponent} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(mockAddComponent).not.toHaveBeenCalled();
    });

    it("should not call addComponent when customComponent is null", async () => {
      const user = userEvent.setup();
      const propsWithNullCustomComponent = {
        ...defaultProps,
        customComponent: null,
      };

      render(<SidebarMenuButtons {...propsWithNullCustomComponent} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(mockAddComponent).not.toHaveBeenCalled();
    });

    it("should handle multiple clicks correctly", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);
      await user.click(customButton);
      await user.click(customButton);

      expect(mockAddComponent).toHaveBeenCalledTimes(3);
      expect(mockAddComponent).toHaveBeenCalledWith(
        mockCustomComponent,
        "CustomComponent",
      );
    });
  });

  describe("Loading State", () => {
    it("should disable custom component button when loading", () => {
      const propsWithLoading = { ...defaultProps, isLoading: true };
      render(<SidebarMenuButtons {...propsWithLoading} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      expect(customButton).toBeDisabled();
    });

    it("should not disable button when not loading", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      expect(customButton).not.toBeDisabled();
    });

    it("should not call addComponent when button is disabled and clicked", async () => {
      const user = userEvent.setup();
      const propsWithLoading = { ...defaultProps, isLoading: true };
      render(<SidebarMenuButtons {...propsWithLoading} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(mockAddComponent).not.toHaveBeenCalled();
    });
  });

  describe("MCP Functionality", () => {
    beforeEach(() => {
      // Mock the sidebar to be in MCP section
      mockUseSidebar.mockReturnValue({
        activeSection: "mcp",
      });
    });

    it("should render MCP buttons when in MCP section", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-add-mcp-server-button"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("sidebar-manage-servers-button"),
      ).toBeInTheDocument();

      // Should not show custom component button
      expect(
        screen.queryByTestId("sidebar-custom-component-button"),
      ).not.toBeInTheDocument();
    });

    it("should render Add MCP Server button with correct content", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      expect(addButton).toHaveTextContent("Add MCP Server");
      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    });

    it("should render Manage Servers button with correct content", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const manageButton = screen.getByTestId("sidebar-manage-servers-button");
      expect(manageButton).toHaveTextContent("Manage Servers");
      expect(screen.getByTestId("icon-ArrowUpRight")).toBeInTheDocument();
    });

    it("should open modal when Add MCP Server button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByTestId("add-mcp-server-modal")).toHaveAttribute(
        "data-open",
        "false",
      );

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      await user.click(addButton);

      expect(screen.getByTestId("add-mcp-server-modal")).toHaveAttribute(
        "data-open",
        "true",
      );
    });

    it("should navigate to settings when Manage Servers button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} />);

      const manageButton = screen.getByTestId("sidebar-manage-servers-button");
      await user.click(manageButton);

      expect(mockNavigate).toHaveBeenCalledWith("/settings/mcp-servers");
      expect(mockNavigate).toHaveBeenCalledTimes(1);
    });

    it("should disable MCP buttons when loading", () => {
      render(<SidebarMenuButtons {...defaultProps} isLoading={true} />);

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      const manageButton = screen.getByTestId("sidebar-manage-servers-button");

      expect(addButton).toBeDisabled();
      expect(manageButton).toBeDisabled();
    });

    it("should close modal when close button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} />);

      // Open modal first
      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      await user.click(addButton);
      expect(screen.getByTestId("add-mcp-server-modal")).toHaveAttribute(
        "data-open",
        "true",
      );

      // Close modal
      const closeButton = screen.getByText("Close Modal");
      await user.click(closeButton);
      expect(screen.getByTestId("add-mcp-server-modal")).toHaveAttribute(
        "data-open",
        "false",
      );
    });

    it("should apply correct styling to MCP buttons", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      const manageButton = screen.getByTestId("sidebar-manage-servers-button");

      expect(addButton).toHaveClass(
        "flex",
        "items-center",
        "w-full",
        "h-full",
        "gap-3",
        "hover:bg-muted",
      );
      expect(addButton).toHaveAttribute("data-unstyled", "true");
      expect(manageButton).toHaveClass(
        "flex",
        "items-center",
        "w-full",
        "h-full",
        "gap-3",
        "hover:bg-muted",
      );
      expect(manageButton).toHaveAttribute("data-unstyled", "true");
    });

    it("should render MCP icons with correct styling", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const plusIcon = screen.getByTestId("icon-Plus");
      const arrowIcon = screen.getByTestId("icon-ArrowUpRight");

      expect(plusIcon).toHaveClass("h-4", "w-4", "text-muted-foreground");
      expect(arrowIcon).toHaveClass("h-4", "w-4", "text-muted-foreground");
    });

    it("should render MCP button text with correct styling", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const addSpan = screen.getByText("Add MCP Server");
      const manageSpan = screen.getByText("Manage Servers");

      expect(addSpan).toHaveClass(
        "group-data-[state=open]/collapsible:font-semibold",
      );
      expect(manageSpan).toHaveClass(
        "group-data-[state=open]/collapsible:font-semibold",
      );
    });

    it("should render modal component", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByTestId("add-mcp-server-modal")).toBeInTheDocument();
    });
  });

  describe("Section Switching", () => {
    it("should show custom component button in components section", () => {
      mockUseSidebar.mockReturnValue({
        activeSection: "components",
      });

      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("sidebar-add-mcp-server-button"),
      ).not.toBeInTheDocument();
    });

    it("should show MCP buttons in mcp section", () => {
      mockUseSidebar.mockReturnValue({
        activeSection: "mcp",
      });

      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-add-mcp-server-button"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("sidebar-custom-component-button"),
      ).not.toBeInTheDocument();
    });

    it("should show custom component button in bundles section", () => {
      mockUseSidebar.mockReturnValue({
        activeSection: "bundles",
      });

      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("sidebar-add-mcp-server-button"),
      ).not.toBeInTheDocument();
    });

    it("should show custom component button in search section", () => {
      mockUseSidebar.mockReturnValue({
        activeSection: "search",
      });

      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("sidebar-add-mcp-server-button"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Component Structure", () => {
    it("should render fragments correctly", () => {
      const { container } = render(<SidebarMenuButtons {...defaultProps} />);

      // Component should render without wrapper elements (using React fragment)
      expect(container.children).toHaveLength(1);
    });

    it("should render custom component button with correct attributes", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      expect(customButton).toHaveAttribute("data-unstyled", "true");
    });

    it("should render multiple SidebarMenuButtons in MCP mode", () => {
      mockUseSidebar.mockReturnValue({
        activeSection: "mcp",
      });

      render(<SidebarMenuButtons {...defaultProps} />);

      const sidebarMenuButtons = screen.getAllByTestId("sidebar-menu-button");
      expect(sidebarMenuButtons).toHaveLength(2); // Add + Manage buttons
    });
  });

  describe("Props Handling", () => {
    it("should handle minimal props correctly", () => {
      const minimalProps = {
        customComponent: mockCustomComponent,
        addComponent: mockAddComponent,
      };

      render(<SidebarMenuButtons {...minimalProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).not.toBeDisabled();
    });

    it("should work with different customComponent objects", async () => {
      const user = userEvent.setup();
      const differentCustomComponent = {
        description: "Different component",
        template: { test: true },
        display_name: "Different Component",
        documentation: "Different docs",
      };

      const propsWithDifferentComponent = {
        ...defaultProps,
        customComponent: differentCustomComponent,
      };

      render(<SidebarMenuButtons {...propsWithDifferentComponent} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(mockAddComponent).toHaveBeenCalledWith(
        differentCustomComponent,
        "CustomComponent",
      );
    });

    it("should work with different addComponent functions", async () => {
      const user = userEvent.setup();
      const alternativeAddComponent = jest.fn();
      const propsWithDifferentAddComponent = {
        ...defaultProps,
        addComponent: alternativeAddComponent,
      };

      render(<SidebarMenuButtons {...propsWithDifferentAddComponent} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(alternativeAddComponent).toHaveBeenCalledWith(
        mockCustomComponent,
        "CustomComponent",
      );
      expect(mockAddComponent).not.toHaveBeenCalled();
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing addComponent function gracefully", () => {
      const propsWithoutAddComponent = {
        ...defaultProps,
        addComponent: undefined,
      };

      expect(() => {
        render(<SidebarMenuButtons {...propsWithoutAddComponent} />);
      }).not.toThrow();
    });

    it("should handle boolean isLoading values", () => {
      const { rerender } = render(
        <SidebarMenuButtons {...defaultProps} isLoading={false} />,
      );
      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).not.toBeDisabled();

      rerender(<SidebarMenuButtons {...defaultProps} isLoading={true} />);
      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeDisabled();
    });

    it("should handle rapid prop changes", () => {
      const { rerender } = render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).not.toBeDisabled();

      rerender(<SidebarMenuButtons {...defaultProps} isLoading={true} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeDisabled();
    });
  });

  describe("Text Content", () => {
    it("should display correct text content in custom mode", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByText("New Custom Component")).toBeInTheDocument();
    });

    it("should display correct text content in MCP mode", () => {
      mockUseSidebar.mockReturnValue({
        activeSection: "mcp",
      });

      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByText("Add MCP Server")).toBeInTheDocument();
      expect(screen.getByText("Manage Servers")).toBeInTheDocument();
    });

    it("should have spans with correct classes", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const customSpan = screen.getByText("New Custom Component");

      expect(customSpan).toHaveClass(
        "group-data-[state=open]/collapsible:font-semibold",
      );
    });

    it("should apply correct styling to custom component button", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      expect(customButton).toHaveClass(
        "flex",
        "items-center",
        "w-full",
        "h-full",
        "gap-3",
        "hover:bg-muted",
      );
      expect(customButton).toHaveAttribute("data-unstyled", "true");
    });

    it("should apply group class to custom component SidebarMenuButton", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const sidebarMenuButton = screen.getByTestId("sidebar-menu-button");
      expect(sidebarMenuButton).toHaveClass("group");
    });
  });

  describe("Callback Behavior", () => {
    it("should call addComponent with exact arguments", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      await user.click(customButton);

      expect(mockAddComponent).toHaveBeenCalledWith(
        mockCustomComponent,
        "CustomComponent",
      );
      expect(mockAddComponent).toHaveBeenCalledTimes(1);

      // Verify the exact call arguments
      const [firstArg, secondArg] = mockAddComponent.mock.calls[0];
      expect(firstArg).toBe(mockCustomComponent);
      expect(secondArg).toBe("CustomComponent");
    });

    it("should handle addComponent throwing errors", async () => {
      const user = userEvent.setup();
      const throwingAddComponent = jest.fn(() => {
        throw new Error("Test error");
      });

      const propsWithThrowingFunction = {
        ...defaultProps,
        addComponent: throwingAddComponent,
      };

      render(<SidebarMenuButtons {...propsWithThrowingFunction} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );

      // Should not crash the component
      expect(async () => {
        await user.click(customButton);
      }).not.toThrow();
    });
  });
});
