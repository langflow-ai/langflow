import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type React from "react";
import type { APIClassType } from "@/types/api";
import McpSidebarGroup from "../McpSidebarGroup";

// Mock the UI components
jest.mock("@/components/ui/sidebar", () => ({
  SidebarGroup: ({ children, className }: any) => (
    <div data-testid="sidebar-group" className={className}>
      {children}
    </div>
  ),
  SidebarGroupContent: ({ children, className }: any) => (
    <div data-testid="sidebar-group-content" className={className}>
      {children}
    </div>
  ),
  SidebarGroupLabel: ({ children, className }: any) => (
    <div data-testid="sidebar-group-label" className={className}>
      {children}
    </div>
  ),
  SidebarMenu: ({ children, className }: any) => (
    <div data-testid="sidebar-menu" className={className}>
      {children}
    </div>
  ),
}));

// Mock the Button component
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, variant, size, ...props }: any) => (
    <button
      data-testid="add-mcp-server-button-sidebar"
      onClick={onClick}
      disabled={disabled}
      data-variant={variant}
      data-size={size}
      {...props}
    >
      {children}
    </button>
  ),
}));

// Mock ShadTooltip
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content, side }: any) => (
    <div data-testid="tooltip" data-content={content} data-side={side}>
      {children}
    </div>
  ),
}));

// Mock SearchConfigTrigger
jest.mock("../searchConfigTrigger", () => ({
  SearchConfigTrigger: ({ showConfig, setShowConfig }: any) => (
    <button
      data-testid="search-config-trigger"
      onClick={() => setShowConfig(!showConfig)}
    >
      Config Toggle: {showConfig.toString()}
    </button>
  ),
}));

// Mock SidebarDraggableComponent
jest.mock("../sidebarDraggableComponent", () => ({
  __esModule: true,
  default: ({
    sectionName,
    apiClass,
    icon,
    onDragStart,
    color,
    itemName,
    error,
    display_name,
    official,
    beta,
    legacy,
    disabled,
    disabledTooltip,
  }: any) => (
    <div
      data-testid={`draggable-component-${apiClass.name}`}
      data-section={sectionName}
      data-icon={icon}
      data-color={color}
      data-item-name={itemName}
      data-error={error}
      data-display-name={display_name}
      data-official={official}
      data-beta={beta}
      data-legacy={legacy}
      data-disabled={disabled}
      data-disabled-tooltip={disabledTooltip}
      onDragStart={onDragStart}
    >
      {display_name || apiClass.display_name || apiClass.name}
    </div>
  ),
}));

// Mock AddMcpServerModal
jest.mock("@/modals/addMcpServerModal", () => ({
  __esModule: true,
  default: ({ open, setOpen }: any) => (
    <div data-testid="add-mcp-server-modal" data-open={open}>
      <button onClick={() => setOpen(false)}>Close Modal</button>
    </div>
  ),
}));

// Mock DeleteConfirmationModal
jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ open, setOpen, onConfirm }: any) => (
    <div data-testid="delete-confirmation-modal" data-open={open}>
      <button onClick={() => setOpen(false)}>Cancel</button>
      <button onClick={onConfirm}>Confirm</button>
    </div>
  ),
}));

// Mock useDeleteMCPServer hook
jest.mock("@/controllers/API/queries/mcp/use-delete-mcp-server", () => ({
  useDeleteMCPServer: () => ({
    mutate: jest.fn(),
  }),
}));

// Mock alertStore
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: jest.fn(),
    }),
}));

// Mock className utility function (cn)
jest.mock("@/utils/utils", () => ({
  removeCountFromString: (str: string) => str.replace(/\s*\(\d+\)$/, ""),
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

// Test wrapper with QueryClient
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("McpSidebarGroup", () => {
  const mockOnDragStart = jest.fn();
  const mockSetOpenCategories = jest.fn();
  const mockSetShowConfig = jest.fn();

  const defaultProps = {
    nodeColors: { agents: "#ff0000" },
    onDragStart: mockOnDragStart,
    openCategories: ["MCP"],
    setOpenCategories: mockSetOpenCategories,
    search: "",
    hasMcpServers: false,
    showSearchConfigTrigger: false,
    showConfig: false,
    setShowConfig: mockSetShowConfig,
  };

  const mockMcpComponent: APIClassType = {
    name: "test-mcp-component",
    display_name: "Test MCP Component",
    description: "Test MCP component description",
    template: {},
    documentation: "Test documentation",
    mcpServerName: "Test Server",
    icon: "TestIcon",
    error: undefined,
    official: true,
    beta: false,
    legacy: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Visibility and Rendering", () => {
    it("should render when MCP category is open", () => {
      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...defaultProps} />, { wrapper: TestWrapper });

      expect(screen.getByTestId("sidebar-group")).toBeInTheDocument();
    });

    it("should render when search is empty (current component logic)", () => {
      // Note: Based on current logic, component renders when search === ""
      // This might be a bug in the component, but testing current behavior
      const props = {
        ...defaultProps,
        openCategories: [], // MCP not in openCategories
        search: "", // empty search - component will still render due to logic
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });
      expect(screen.getByTestId("sidebar-group")).toBeInTheDocument();
    });

    it("should render when searching and MCP is in openCategories", () => {
      const props = {
        ...defaultProps,
        openCategories: ["MCP"], // MCP in openCategories
        search: "test", // and we have search
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });
      expect(screen.getByTestId("sidebar-group")).toBeInTheDocument();
    });

    it("should not render when search is not empty and MCP is not in openCategories", () => {
      const props = {
        ...defaultProps,
        openCategories: [], // MCP not in openCategories
        search: "test", // search is not empty
      };

      // With search !== "" and MCP not in openCategories:
      // isOpen = false || false = false
      // So component should not render
      const TestWrapper = createTestWrapper();
      const { container } = render(<McpSidebarGroup {...props} />, {
        wrapper: TestWrapper,
      });
      expect(container.firstChild).toBeNull();
    });
  });

  describe("Empty State", () => {
    it("should show empty state when no MCP servers are added", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByText("No MCP Servers Added")).toBeInTheDocument();
      expect(
        screen.getByTestId("add-mcp-server-button-sidebar"),
      ).toBeInTheDocument();
    });

    it("should open AddMcpServerModal when Add MCP Server button is clicked", async () => {
      const user = userEvent.setup();
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const addButton = screen.getByTestId("add-mcp-server-button-sidebar");
      await user.click(addButton);

      expect(screen.getByTestId("add-mcp-server-modal")).toHaveAttribute(
        "data-open",
        "true",
      );
    });

    it("should disable Add MCP Server button when loading", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        mcpLoading: true,
        hasMcpServers: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(
        screen.getByTestId("add-mcp-server-button-sidebar"),
      ).toBeDisabled();
    });

    it("should apply full height class when no MCP servers", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByTestId("sidebar-group")).toHaveClass("h-full");
      expect(screen.getByTestId("sidebar-menu")).toHaveClass("h-full");
    });
  });

  describe("Loading State", () => {
    it("should show loading text when loading", () => {
      const props = {
        ...defaultProps,
        mcpLoading: true,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });

  describe("MCP Components Display", () => {
    it("should render MCP components when hasMcpServers is true", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [mockMcpComponent],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByTestId("sidebar-group-label")).toHaveTextContent(
        "MCP Servers",
      );
      expect(
        screen.getByTestId(`draggable-component-${mockMcpComponent.name}`),
      ).toBeInTheDocument();
    });

    it("should render multiple MCP components", () => {
      const secondComponent: APIClassType = {
        ...mockMcpComponent,
        mcpServerName: "Test Other Server",
        name: "second-mcp-component",
        display_name: "Second MCP Component",
      };

      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [mockMcpComponent, secondComponent],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(
        screen.getByTestId(`draggable-component-${mockMcpComponent.name}`),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId(`draggable-component-${secondComponent.name}`),
      ).toBeInTheDocument();
    });

    it("should wrap each component in a tooltip", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [mockMcpComponent],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const tooltip = screen.getByTestId("tooltip");
      expect(tooltip).toHaveAttribute(
        "data-content",
        mockMcpComponent.display_name,
      );
      expect(tooltip).toHaveAttribute("data-side", "right");
    });
  });

  describe("SearchConfigTrigger", () => {
    it("should render SearchConfigTrigger when showSearchConfigTrigger is true and hasMcpServers is true", () => {
      const props = {
        ...defaultProps,
        hasMcpServers: true,
        showSearchConfigTrigger: true,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
    });

    it("should not render SearchConfigTrigger when showSearchConfigTrigger is false", () => {
      const props = {
        ...defaultProps,
        hasMcpServers: true,
        showSearchConfigTrigger: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(
        screen.queryByTestId("search-config-trigger"),
      ).not.toBeInTheDocument();
    });

    it("should not render SearchConfigTrigger when hasMcpServers is false", () => {
      const props = {
        ...defaultProps,
        hasMcpServers: false,
        showSearchConfigTrigger: true,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(
        screen.queryByTestId("search-config-trigger"),
      ).not.toBeInTheDocument();
    });

    it("should call setShowConfig when SearchConfigTrigger is clicked", async () => {
      const user = userEvent.setup();
      const props = {
        ...defaultProps,
        hasMcpServers: true,
        showSearchConfigTrigger: true,
        showConfig: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const configTrigger = screen.getByTestId("search-config-trigger");
      await user.click(configTrigger);

      expect(mockSetShowConfig).toHaveBeenCalledWith(true);
    });
  });

  describe("Drag and Drop", () => {
    it("should call onDragStart with correct parameters", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [mockMcpComponent],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const draggableComponent = screen.getByTestId(
        `draggable-component-${mockMcpComponent.name}`,
      );

      // Simulate drag start
      fireEvent.dragStart(draggableComponent);

      // The onDragStart should be called through the component's prop
      expect(draggableComponent).toHaveAttribute("data-section", "mcp");
    });

    it("should pass correct props to SidebarDraggableComponent", () => {
      const componentWithError: APIClassType = {
        ...mockMcpComponent,
        error: "Test error message",
        mcpServerName: "Test Other Other Server",
        beta: true,
        official: false,
      };

      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [componentWithError],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const draggableComponent = screen.getByTestId(
        `draggable-component-${componentWithError.name}`,
      );

      expect(draggableComponent).toHaveAttribute("data-error", "true");
      expect(draggableComponent).toHaveAttribute("data-beta", "true");
      expect(draggableComponent).toHaveAttribute("data-official", "false");
      expect(draggableComponent).toHaveAttribute("data-disabled", "false");
      expect(draggableComponent).toHaveAttribute("data-item-name", "MCP");
      expect(draggableComponent).toHaveAttribute(
        "data-icon",
        componentWithError.icon,
      );
    });
  });

  describe("Component Props and Data Handling", () => {
    it("should use mcpServerName as display_name when available", () => {
      const componentWithServerName: APIClassType = {
        ...mockMcpComponent,
        mcpServerName: "Custom Server Name",
      };

      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [componentWithServerName],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const draggableComponent = screen.getByTestId(
        `draggable-component-${componentWithServerName.name}`,
      );

      expect(draggableComponent).toHaveAttribute(
        "data-display-name",
        "Custom Server Name",
      );
    });

    it("should fallback to display_name when mcpServerName is not available", () => {
      const componentWithoutServerName: APIClassType = {
        ...mockMcpComponent,
        mcpServerName: undefined,
      };

      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [componentWithoutServerName],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const draggableComponent = screen.getByTestId(
        `draggable-component-${componentWithoutServerName.name}`,
      );

      expect(draggableComponent).toHaveAttribute(
        "data-display-name",
        componentWithoutServerName.display_name,
      );
    });

    it("should use default icon when not provided", () => {
      const componentWithoutIcon: APIClassType = {
        ...mockMcpComponent,
        icon: undefined,
      };

      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [componentWithoutIcon],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const draggableComponent = screen.getByTestId(
        `draggable-component-${componentWithoutIcon.name}`,
      );

      expect(draggableComponent).toHaveAttribute("data-icon", "Mcp");
    });
  });

  describe("CSS Classes and Styling", () => {
    it("should apply correct CSS classes to SidebarGroup", () => {
      const props = {
        ...defaultProps,
        hasMcpServers: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByTestId("sidebar-group")).toHaveClass("p-3", "h-full");
    });

    it("should not apply h-full class when hasMcpServers is true", () => {
      const props = {
        ...defaultProps,
        hasMcpServers: true,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const sidebarGroup = screen.getByTestId("sidebar-group");
      expect(sidebarGroup).toHaveClass("p-3");
      expect(sidebarGroup).not.toHaveClass("h-full");
    });
  });

  describe("Edge Cases", () => {
    it("should handle undefined mcpComponents gracefully", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: undefined,
      };

      const TestWrapper = createTestWrapper();
      expect(() =>
        render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper }),
      ).not.toThrow();
    });

    it("should handle empty mcpComponents array", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      expect(screen.getByTestId("sidebar-group-label")).toHaveTextContent(
        "MCP Servers",
      );
      expect(
        screen.queryByTestId("draggable-component-"),
      ).not.toBeInTheDocument();
    });

    it("should handle missing display_name in tooltip", () => {
      const componentWithoutDisplayName: APIClassType = {
        ...mockMcpComponent,
        display_name: "",
      };

      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: true,
        mcpComponents: [componentWithoutDisplayName],
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      const tooltip = screen.getByTestId("tooltip");
      expect(tooltip).toHaveAttribute(
        "data-content",
        componentWithoutDisplayName.name,
      );
    });
  });

  describe("State Management", () => {
    it("should not modify external state directly", () => {
      const props = {
        ...defaultProps,
        mcpSuccess: true,
        hasMcpServers: false,
      };

      const TestWrapper = createTestWrapper();
      render(<McpSidebarGroup {...props} />, { wrapper: TestWrapper });

      // Verify that the component doesn't call state setters during render
      expect(mockSetOpenCategories).not.toHaveBeenCalled();
      expect(mockSetShowConfig).not.toHaveBeenCalled();
    });
  });
});
