import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import SidebarMenuButtons from "../sidebarFooterButtons";

// Mock the UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: any) => (
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
  }: any) => (
    <button
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

jest.mock("@/components/ui/sidebar", () => ({
  SidebarMenuButton: ({ children, asChild }: any) => (
    <div data-testid="sidebar-menu-button" data-as-child={asChild}>
      {children}
    </div>
  ),
  useSidebar: () => ({
    activeSection: "components",
  }),
}));

jest.mock("@/customization/components/custom-link", () => ({
  CustomLink: ({ children, to, target, rel, className }: any) => (
    <a
      data-testid="custom-link"
      href={to}
      target={target}
      rel={rel}
      className={className}
    >
      {children}
    </a>
  ),
}));

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_LANGFLOW_STORE: true,
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
  default: ({ open, setOpen }: any) => (
    <div data-testid="add-mcp-server-modal" data-open={open}>
      <button onClick={() => setOpen(false)}>Close Modal</button>
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
    hasStore: false,
    customComponent: mockCustomComponent,
    addComponent: mockAddComponent,
    isLoading: false,
    hasMcpServers: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockNavigate.mockClear();
  });

  describe("Basic Rendering", () => {
    it("should render custom component button", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
      expect(screen.getByText("New Custom Component")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    });

    it("should render sidebar menu buttons", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.getByTestId("sidebar-menu-button")).toBeInTheDocument();
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

  describe("Store Link Rendering", () => {
    it("should not render store link when hasStore is false", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      expect(screen.queryByTestId("custom-link")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Discover more components"),
      ).not.toBeInTheDocument();
    });

    it("should render store link when hasStore is true", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      expect(screen.getByTestId("custom-link")).toBeInTheDocument();
      expect(screen.getByText("Discover more components")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Store")).toBeInTheDocument();
      expect(
        screen.getByTestId("icon-SquareArrowOutUpRight"),
      ).toBeInTheDocument();
    });

    it("should render store link with correct attributes", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const storeLink = screen.getByTestId("custom-link");
      expect(storeLink).toHaveAttribute("href", "/store");
      expect(storeLink).toHaveAttribute("target", "_blank");
      expect(storeLink).toHaveAttribute("rel", "noopener noreferrer");
    });

    it("should render store link inside sidebar menu button", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const sidebarMenuButtons = screen.getAllByTestId("sidebar-menu-button");
      expect(sidebarMenuButtons).toHaveLength(2); // Store link + custom component button
      expect(sidebarMenuButtons[0]).toContainElement(
        screen.getByTestId("custom-link"),
      );
    });

    it("should render store icons correctly", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      expect(screen.getByTestId("icon-Store")).toBeInTheDocument();
      expect(
        screen.getByTestId("icon-SquareArrowOutUpRight"),
      ).toBeInTheDocument();
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

  describe("Component Structure", () => {
    it("should have correct DOM hierarchy without store", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const sidebarMenuButtons = screen.getAllByTestId("sidebar-menu-button");
      expect(sidebarMenuButtons).toHaveLength(1);
      expect(sidebarMenuButtons[0]).toContainElement(
        screen.getByTestId("sidebar-custom-component-button"),
      );
    });

    it("should have correct DOM hierarchy with store", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const sidebarMenuButtons = screen.getAllByTestId("sidebar-menu-button");
      expect(sidebarMenuButtons).toHaveLength(2);
      expect(sidebarMenuButtons[0]).toContainElement(
        screen.getByTestId("custom-link"),
      );
      expect(sidebarMenuButtons[1]).toContainElement(
        screen.getByTestId("sidebar-custom-component-button"),
      );
    });

    it("should render fragments correctly", () => {
      const { container } = render(<SidebarMenuButtons {...defaultProps} />);

      // Component should render without wrapper elements (using React fragment)
      expect(container.children).toHaveLength(1);
    });
  });

  describe("CSS Classes", () => {
    it("should apply correct classes to custom component button", () => {
      render(<SidebarMenuButtons {...defaultProps} />);

      const customButton = screen.getByTestId(
        "sidebar-custom-component-button",
      );
      expect(customButton).toHaveClass("flex", "items-center", "gap-2");
      expect(customButton).toHaveAttribute("data-unstyled", "true");
    });

    it("should apply correct classes to store link", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const storeLink = screen.getByTestId("custom-link");
      expect(storeLink).toHaveClass("group/discover");
    });

    it("should apply correct classes to icons", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const storeIcon = screen.getByTestId("icon-Store");
      const arrowIcon = screen.getByTestId("icon-SquareArrowOutUpRight");
      const plusIcon = screen.getByTestId("icon-Plus");

      expect(storeIcon).toHaveClass("h-4", "w-4", "text-muted-foreground");
      expect(arrowIcon).toHaveClass(
        "h-4",
        "w-4",
        "opacity-0",
        "transition-all",
        "group-hover/discover:opacity-100",
      );
      expect(plusIcon).toHaveClass("h-4", "w-4", "text-muted-foreground");
    });
  });

  describe("Props Handling", () => {
    it("should handle default props correctly", () => {
      const minimalProps = {
        addComponent: mockAddComponent,
      };

      render(<SidebarMenuButtons {...minimalProps} />);

      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).not.toBeDisabled();
      expect(screen.queryByTestId("custom-link")).not.toBeInTheDocument();
    });

    it("should handle all props provided", () => {
      const fullProps = {
        hasStore: true,
        customComponent: mockCustomComponent,
        addComponent: mockAddComponent,
        isLoading: true,
      };

      render(<SidebarMenuButtons {...fullProps} />);

      expect(screen.getByTestId("custom-link")).toBeInTheDocument();
      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeDisabled();
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

    it("should handle boolean hasStore values", () => {
      const { rerender } = render(
        <SidebarMenuButtons {...defaultProps} hasStore={false} />,
      );
      expect(screen.queryByTestId("custom-link")).not.toBeInTheDocument();

      rerender(<SidebarMenuButtons {...defaultProps} hasStore={true} />);
      expect(screen.getByTestId("custom-link")).toBeInTheDocument();
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

      expect(screen.queryByTestId("custom-link")).not.toBeInTheDocument();
      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).not.toBeDisabled();

      rerender(
        <SidebarMenuButtons
          {...defaultProps}
          hasStore={true}
          isLoading={true}
        />,
      );

      expect(screen.getByTestId("custom-link")).toBeInTheDocument();
      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeDisabled();
    });
  });

  describe("Text Content", () => {
    it("should display correct text content", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      expect(screen.getByText("Discover more components")).toBeInTheDocument();
      expect(screen.getByText("New Custom Component")).toBeInTheDocument();
    });

    it("should have spans with correct classes", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const storeSpan = screen.getByText("Discover more components");
      const customSpan = screen.getByText("New Custom Component");

      expect(storeSpan).toHaveClass(
        "flex-1",
        "group-data-[state=open]/collapsible:font-semibold",
      );
      expect(customSpan).toHaveClass(
        "group-data-[state=open]/collapsible:font-semibold",
      );
    });
  });

  describe("SidebarMenuButton Integration", () => {
    it("should render SidebarMenuButton with asChild prop", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const sidebarMenuButtons = screen.getAllByTestId("sidebar-menu-button");
      sidebarMenuButtons.forEach((button) => {
        expect(button).toHaveAttribute("data-as-child", "true");
      });
    });

    it("should wrap both store link and custom button in SidebarMenuButton", () => {
      const propsWithStore = { ...defaultProps, hasStore: true };
      render(<SidebarMenuButtons {...propsWithStore} />);

      const sidebarMenuButtons = screen.getAllByTestId("sidebar-menu-button");
      expect(sidebarMenuButtons).toHaveLength(2);
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

  describe("MCP Functionality", () => {
    beforeEach(() => {
      // Mock the sidebar to be in MCP section
      jest
        .mocked(require("@/components/ui/sidebar").useSidebar)
        .mockReturnValue({
          activeSection: "mcp",
        });
    });

    it("should not render MCP buttons when hasMcpServers is false", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={false} />);

      expect(
        screen.queryByTestId("sidebar-add-mcp-server-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("sidebar-manage-servers-button"),
      ).not.toBeInTheDocument();
    });

    it("should render MCP buttons when hasMcpServers is true and in MCP section", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      expect(
        screen.getByTestId("sidebar-add-mcp-server-button"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("sidebar-manage-servers-button"),
      ).toBeInTheDocument();
    });

    it("should render Add MCP Server button with correct content", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      expect(addButton).toHaveTextContent("Add MCP Server");
      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    });

    it("should render Manage Servers button with correct content", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      const manageButton = screen.getByTestId("sidebar-manage-servers-button");
      expect(manageButton).toHaveTextContent("Manage Servers");
      expect(screen.getByTestId("icon-ArrowUpRight")).toBeInTheDocument();
    });

    it("should open modal when Add MCP Server button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

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
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      const manageButton = screen.getByTestId("sidebar-manage-servers-button");
      await user.click(manageButton);

      expect(mockNavigate).toHaveBeenCalledWith("/settings/mcp-servers");
      expect(mockNavigate).toHaveBeenCalledTimes(1);
    });

    it("should disable MCP buttons when loading", () => {
      render(
        <SidebarMenuButtons
          {...defaultProps}
          hasMcpServers={true}
          isLoading={true}
        />,
      );

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      const manageButton = screen.getByTestId("sidebar-manage-servers-button");

      expect(addButton).toBeDisabled();
      expect(manageButton).toBeDisabled();
    });

    it("should close modal when close button is clicked", async () => {
      const user = userEvent.setup();
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

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

    it("should not render MCP buttons in non-MCP sections", () => {
      // Mock the sidebar to be in components section
      jest
        .mocked(require("@/components/ui/sidebar").useSidebar)
        .mockReturnValue({
          activeSection: "components",
        });

      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      expect(
        screen.queryByTestId("sidebar-add-mcp-server-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("sidebar-manage-servers-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId("sidebar-custom-component-button"),
      ).toBeInTheDocument();
    });

    it("should apply correct styling to MCP buttons", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      const addButton = screen.getByTestId("sidebar-add-mcp-server-button");
      const manageButton = screen.getByTestId("sidebar-manage-servers-button");

      expect(addButton).toHaveClass("flex", "items-center", "gap-2");
      expect(addButton).toHaveAttribute("data-unstyled", "true");
      expect(manageButton).toHaveClass("flex", "items-center", "gap-2");
      expect(manageButton).toHaveAttribute("data-unstyled", "true");
    });

    it("should render MCP icons with correct styling", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      const plusIcon = screen.getByTestId("icon-Plus");
      const arrowIcon = screen.getByTestId("icon-ArrowUpRight");

      expect(plusIcon).toHaveClass("h-4", "w-4", "text-muted-foreground");
      expect(arrowIcon).toHaveClass("h-4", "w-4", "text-muted-foreground");
    });

    it("should render MCP button text with correct styling", () => {
      render(<SidebarMenuButtons {...defaultProps} hasMcpServers={true} />);

      const addSpan = screen.getByText("Add MCP Server");
      const manageSpan = screen.getByText("Manage Servers");

      expect(addSpan).toHaveClass(
        "group-data-[state=open]/collapsible:font-semibold",
      );
      expect(manageSpan).toHaveClass(
        "group-data-[state=open]/collapsible:font-semibold",
      );
    });
  });
});
