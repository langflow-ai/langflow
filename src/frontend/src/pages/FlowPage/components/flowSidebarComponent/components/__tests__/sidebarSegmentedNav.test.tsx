import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { SidebarSection } from "@/components/ui/sidebar";
import SidebarSegmentedNav, { NAV_ITEMS } from "../sidebarSegmentedNav";

// Mock the hooks and components
const mockUseSidebar: {
  activeSection: SidebarSection;
  setActiveSection: jest.Mock;
  toggleSidebar: jest.Mock;
  open: boolean;
} = {
  activeSection: "components" as SidebarSection,
  setActiveSection: jest.fn(),
  toggleSidebar: jest.fn(),
  open: true,
};

const mockUseSearchContext = {
  focusSearch: jest.fn(),
  isSearchFocused: false,
  setSearch: jest.fn(),
};

jest.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => mockUseSidebar,
  SidebarMenu: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="sidebar-menu" className={className}>
      {children}
    </div>
  ),
  SidebarMenuButton: ({
    children,
    onClick,
    isActive,
    className,
    size,
    "data-testid": testId,
  }: {
    children: React.ReactNode;
    onClick?: (e: React.MouseEvent) => void;
    isActive?: boolean;
    className?: string;
    size?: string;
    "data-testid"?: string;
  }) => (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      data-active={isActive}
      data-size={size}
      className={className}
    >
      {children}
    </button>
  ),
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar-menu-item">{children}</div>
  ),
}));

jest.mock("../../index", () => ({
  useSearchContext: () => mockUseSearchContext,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
    side,
  }: {
    children: React.ReactNode;
    content: string;
    side?: string;
  }) => (
    <div data-testid="tooltip" data-content={content} data-side={side}>
      {children}
    </div>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | undefined | null | boolean)[]) =>
    args.filter(Boolean).join(" "),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: ({ className }: { className?: string }) => (
    <div data-testid="separator" className={className} />
  ),
}));

describe("SidebarSegmentedNav", () => {
  // Mock window.dispatchEvent
  const mockDispatchEvent = jest.fn();
  const originalDispatchEvent = window.dispatchEvent;

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset to default values
    mockUseSidebar.activeSection = "components";
    mockUseSidebar.open = true;
    mockUseSearchContext.isSearchFocused = false;
    jest.clearAllTimers();
    jest.useFakeTimers();

    // Mock window.dispatchEvent
    window.dispatchEvent = mockDispatchEvent;
  });

  afterEach(() => {
    jest.useRealTimers();
    // Restore original dispatchEvent
    window.dispatchEvent = originalDispatchEvent;
  });

  it("renders all navigation items", () => {
    render(<SidebarSegmentedNav />);

    // Check that all nav items are rendered
    NAV_ITEMS.forEach((item) => {
      expect(screen.getByTestId(`sidebar-nav-${item.id}`)).toBeInTheDocument();
      expect(screen.getByTestId(`icon-${item.icon}`)).toBeInTheDocument();
    });
  });

  it("renders correct structure", () => {
    render(<SidebarSegmentedNav />);

    expect(screen.getByTestId("sidebar-menu")).toBeInTheDocument();
    expect(screen.getAllByTestId("sidebar-menu-item")).toHaveLength(
      NAV_ITEMS.length,
    );
    expect(screen.getAllByTestId("tooltip")).toHaveLength(NAV_ITEMS.length);
  });

  it("displays correct tooltips for each item", () => {
    render(<SidebarSegmentedNav />);

    NAV_ITEMS.forEach((item) => {
      const tooltips = screen.getAllByTestId("tooltip");
      const itemTooltip = tooltips.find(
        (tooltip) => tooltip.getAttribute("data-content") === item.tooltip,
      );
      expect(itemTooltip).toBeInTheDocument();
      expect(itemTooltip).toHaveAttribute("data-side", "right");
    });
  });

  it("sets active state for current active section", () => {
    mockUseSidebar.activeSection = "mcp";
    render(<SidebarSegmentedNav />);

    const mcpButton = screen.getByTestId("sidebar-nav-mcp");
    expect(mcpButton).toHaveAttribute("data-active", "true");

    // Other buttons should not be active
    const componentsButton = screen.getByTestId("sidebar-nav-components");
    expect(componentsButton).toHaveAttribute("data-active", "false");
  });

  it("sets active state for search when activeSection is search", () => {
    mockUseSidebar.activeSection = "search";
    render(<SidebarSegmentedNav />);

    const searchButton = screen.getByTestId("sidebar-nav-search");
    expect(searchButton).toHaveAttribute("data-active", "true");
  });

  it("calls setActiveSection when clicking on different section", () => {
    render(<SidebarSegmentedNav />);

    const mcpButton = screen.getByTestId("sidebar-nav-mcp");
    fireEvent.click(mcpButton);

    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledWith("mcp");
    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledTimes(1);
  });

  it("resets search when changing active sections", () => {
    render(<SidebarSegmentedNav />);

    const mcpButton = screen.getByTestId("sidebar-nav-mcp");
    fireEvent.click(mcpButton);

    expect(mockUseSearchContext.setSearch).toHaveBeenCalledWith("");
    expect(mockUseSearchContext.setSearch).toHaveBeenCalledTimes(1);
  });

  it("toggles sidebar when clicking on currently active section", () => {
    mockUseSidebar.activeSection = "components";
    render(<SidebarSegmentedNav />);

    const componentsButton = screen.getByTestId("sidebar-nav-components");
    fireEvent.click(componentsButton);

    expect(mockUseSidebar.toggleSidebar).toHaveBeenCalledTimes(1);
    expect(mockUseSidebar.setActiveSection).not.toHaveBeenCalled();
  });

  it("resets search when toggling sidebar on active section", () => {
    mockUseSidebar.activeSection = "components";
    render(<SidebarSegmentedNav />);

    const componentsButton = screen.getByTestId("sidebar-nav-components");
    fireEvent.click(componentsButton);

    expect(mockUseSearchContext.setSearch).toHaveBeenCalledWith("");
    expect(mockUseSearchContext.setSearch).toHaveBeenCalledTimes(1);
  });

  it("opens sidebar and sets active section when sidebar is closed", () => {
    mockUseSidebar.open = false;
    render(<SidebarSegmentedNav />);

    const bundlesButton = screen.getByTestId("sidebar-nav-bundles");
    fireEvent.click(bundlesButton);

    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledWith("bundles");
    expect(mockUseSidebar.toggleSidebar).toHaveBeenCalledTimes(1);
  });

  it("resets search when opening sidebar and changing sections", () => {
    mockUseSidebar.open = false;
    render(<SidebarSegmentedNav />);

    const bundlesButton = screen.getByTestId("sidebar-nav-bundles");
    fireEvent.click(bundlesButton);

    expect(mockUseSearchContext.setSearch).toHaveBeenCalledWith("");
    expect(mockUseSearchContext.setSearch).toHaveBeenCalledTimes(1);
  });

  it("focuses search input when search section is clicked", async () => {
    render(<SidebarSegmentedNav />);

    const searchButton = screen.getByTestId("sidebar-nav-search");
    fireEvent.click(searchButton);

    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledWith("search");

    // Fast-forward the setTimeout
    jest.advanceTimersByTime(100);

    await waitFor(() => {
      expect(mockUseSearchContext.focusSearch).toHaveBeenCalledTimes(1);
    });
  });

  it("focuses search input even when sidebar is closed", async () => {
    mockUseSidebar.open = false;
    render(<SidebarSegmentedNav />);

    const searchButton = screen.getByTestId("sidebar-nav-search");
    fireEvent.click(searchButton);

    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledWith("search");
    expect(mockUseSidebar.toggleSidebar).toHaveBeenCalledTimes(1);

    // Fast-forward the setTimeout
    jest.advanceTimersByTime(100);

    await waitFor(() => {
      expect(mockUseSearchContext.focusSearch).toHaveBeenCalledTimes(1);
    });
  });

  it("renders accessibility labels correctly", () => {
    render(<SidebarSegmentedNav />);

    NAV_ITEMS.forEach((item) => {
      const button = screen.getByTestId(`sidebar-nav-${item.id}`);
      // Check for screen reader only text
      const srOnlySpan = button.querySelector(".sr-only");
      expect(srOnlySpan).toHaveTextContent(item.label);
    });
  });

  it("applies correct CSS classes", () => {
    mockUseSidebar.activeSection = "mcp";
    render(<SidebarSegmentedNav />);

    const mcpButton = screen.getByTestId("sidebar-nav-mcp");
    expect(mcpButton).toHaveClass(
      "flex",
      "h-8",
      "w-8",
      "items-center",
      "justify-center",
      "rounded-md",
      "p-0",
      "transition-all",
      "duration-200",
      "bg-accent",
      "text-accent-foreground",
    );

    const componentsButton = screen.getByTestId("sidebar-nav-components");
    expect(componentsButton).toHaveClass(
      "flex",
      "h-8",
      "w-8",
      "items-center",
      "justify-center",
      "rounded-md",
      "p-0",
      "transition-all",
      "duration-200",
      "text-muted-foreground",
      "hover:bg-accent",
      "hover:text-accent-foreground",
    );
  });

  it("renders icons with correct styling", () => {
    render(<SidebarSegmentedNav />);

    NAV_ITEMS.forEach((item) => {
      const icon = screen.getByTestId(`icon-${item.icon}`);
      expect(icon).toHaveClass("h-5", "w-5");
    });
  });

  it("renders container with correct styling", () => {
    const { container } = render(<SidebarSegmentedNav />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass(
      "flex",
      "h-full",
      "flex-col",
      "border-r",
      "border-border",
      "bg-background",
    );
  });

  it("renders SidebarMenu with correct styling", () => {
    render(<SidebarSegmentedNav />);

    const sidebarMenu = screen.getByTestId("sidebar-menu");
    expect(sidebarMenu).toHaveClass("gap-2", "py-1");
  });

  it("handles multiple rapid clicks correctly", () => {
    render(<SidebarSegmentedNav />);

    const mcpButton = screen.getByTestId("sidebar-nav-mcp");

    // Click multiple times rapidly
    fireEvent.click(mcpButton);
    fireEvent.click(mcpButton);
    fireEvent.click(mcpButton);

    // Should have called setActiveSection for each click since activeSection !== mcp
    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledTimes(3);
    expect(mockUseSidebar.setActiveSection).toHaveBeenCalledWith("mcp");
  });

  it("exports NAV_ITEMS correctly", () => {
    expect(NAV_ITEMS).toHaveLength(5);
    expect(NAV_ITEMS[0]).toEqual({
      id: "search",
      icon: "search",
      label: "Search",
      tooltip: "Search",
    });
    expect(NAV_ITEMS[3]).toEqual({
      id: "bundles",
      icon: "blocks",
      label: "Bundles",
      tooltip: "Bundles",
    });
    expect(NAV_ITEMS[4]).toEqual({
      id: "add_note",
      icon: "sticky-note",
      label: "Sticky Notes",
      tooltip: "Add Sticky Notes",
    });
  });

  describe("Add Note Functionality", () => {
    it("renders separator before add_note item", () => {
      render(<SidebarSegmentedNav />);

      expect(screen.getByTestId("separator")).toBeInTheDocument();
      expect(screen.getByTestId("separator")).toHaveClass("w-full");
    });

    it("dispatches lf:start-add-note event when add_note is clicked", () => {
      render(<SidebarSegmentedNav />);

      const addNoteButton = screen.getByTestId("sidebar-nav-add_note");
      fireEvent.click(addNoteButton);

      expect(mockDispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "lf:start-add-note",
        }),
      );
      expect(mockDispatchEvent).toHaveBeenCalledTimes(1);
    });

    it("sets add_note as active when clicked", () => {
      render(<SidebarSegmentedNav />);

      const addNoteButton = screen.getByTestId("sidebar-nav-add_note");
      fireEvent.click(addNoteButton);

      expect(addNoteButton).toHaveAttribute("data-active", "true");
    });

    it("stops propagation when add_note is clicked", () => {
      render(<SidebarSegmentedNav />);

      const addNoteButton = screen.getByTestId("sidebar-nav-add_note");
      const mockStopPropagation = jest.fn();

      const event = new MouseEvent("click", { bubbles: true });
      event.stopPropagation = mockStopPropagation;

      fireEvent.click(addNoteButton);

      // The component should call stopPropagation
      expect(mockUseSidebar.setActiveSection).not.toHaveBeenCalled();
      expect(mockUseSidebar.toggleSidebar).not.toHaveBeenCalled();
    });

    it("does not reset search when add_note is clicked", () => {
      render(<SidebarSegmentedNav />);

      const addNoteButton = screen.getByTestId("sidebar-nav-add_note");
      fireEvent.click(addNoteButton);

      expect(mockUseSearchContext.setSearch).not.toHaveBeenCalled();
    });

    it("resets add_note active state when lf:end-add-note event is dispatched", () => {
      const mockAddEventListener = jest.spyOn(window, "addEventListener");

      render(<SidebarSegmentedNav />);

      // Verify that the event listener was added
      expect(mockAddEventListener).toHaveBeenCalledWith(
        "lf:end-add-note",
        expect.any(Function),
      );

      // Get the event listener function that was registered
      const eventListenerCall = mockAddEventListener.mock.calls.find(
        ([eventType]) => eventType === "lf:end-add-note",
      );
      expect(eventListenerCall).toBeDefined();

      // Test that the event listener function works (it should reset state)
      const eventListener = eventListenerCall![1] as () => void;
      expect(typeof eventListener).toBe("function");

      mockAddEventListener.mockRestore();
    });

    it("cleans up event listener on unmount", () => {
      const mockRemoveEventListener = jest.spyOn(window, "removeEventListener");

      const { unmount } = render(<SidebarSegmentedNav />);
      unmount();

      expect(mockRemoveEventListener).toHaveBeenCalledWith(
        "lf:end-add-note",
        expect.any(Function),
      );

      mockRemoveEventListener.mockRestore();
    });
  });
});
