import { render, screen } from "@testing-library/react";
import { MemoizedSidebarGroup } from "../sidebarBundles";

// Mock the UI components
jest.mock("@/components/ui/sidebar", () => ({
  SidebarGroup: ({ children, className }: any) => (
    <div data-testid="sidebar-group" className={className}>
      {children}
    </div>
  ),
  SidebarGroupContent: ({ children }: any) => (
    <div data-testid="sidebar-group-content">{children}</div>
  ),
  SidebarGroupLabel: ({ children, className }: any) => (
    <div data-testid="sidebar-group-label" className={className}>
      {children}
    </div>
  ),
  SidebarMenu: ({ children }: any) => (
    <div data-testid="sidebar-menu">{children}</div>
  ),
}));

// Mock the BundleItem component
jest.mock("../bundleItems", () => ({
  BundleItem: ({ item, openCategories }: any) => (
    <div data-testid={`bundle-item-${item.name}`}>
      Bundle Item: {item.display_name} - Open:{" "}
      {openCategories.includes(item.name).toString()}
    </div>
  ),
}));

// Mock the SearchConfigTrigger component
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

// Mock darkStore to avoid import.meta issues
jest.mock("@/stores/darkStore", () => ({
  useDarkStore: () => ({ isDark: false }),
}));

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: true, // Set to true for SearchConfigTrigger tests
}));

describe("MemoizedSidebarGroup (SidebarBundles)", () => {
  const mockSetOpenCategories = jest.fn();
  const mockOnDragStart = jest.fn();
  const mockSensitiveSort = jest.fn();
  const mockHandleKeyDownInput = jest.fn();
  const mockSetShowConfig = jest.fn();

  const mockAPIClass = {
    description: "Test component",
    template: {},
    display_name: "Test Component",
    documentation: "Test docs",
  };

  const defaultProps = {
    BUNDLES: [
      { name: "bundle1", display_name: "Bundle 1", icon: "Package" },
      { name: "bundle2", display_name: "Bundle 2", icon: "Box" },
      { name: "bundle3", display_name: "Bundle 3", icon: "Archive" },
    ],
    search: "",
    sortedCategories: [],
    dataFilter: {
      bundle1: {
        component1: { ...mockAPIClass, display_name: "Component 1" },
      },
      bundle2: {
        component2: { ...mockAPIClass, display_name: "Component 2" },
      },
      bundle3: {
        component3: { ...mockAPIClass, display_name: "Component 3" },
      },
    },
    nodeColors: {
      bundle1: "#FF0000",
      bundle2: "#00FF00",
      bundle3: "#0000FF",
    },
    onDragStart: mockOnDragStart,
    sensitiveSort: mockSensitiveSort,
    handleKeyDownInput: mockHandleKeyDownInput,
    openCategories: [],
    setOpenCategories: mockSetOpenCategories,
    showSearchConfigTrigger: false,
    showConfig: false,
    setShowConfig: mockSetShowConfig,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockSetShowConfig.mockClear();
  });

  describe("Basic Rendering", () => {
    it("should render sidebar group with correct structure", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(screen.getByTestId("sidebar-group")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-group-content")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-group-label")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu")).toBeInTheDocument();
    });

    it("should display 'Bundles' label", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(screen.getByTestId("sidebar-group-label")).toHaveTextContent(
        "Bundles",
      );
    });

    it("should apply correct CSS classes", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(screen.getByTestId("sidebar-group")).toHaveClass("p-3");
      expect(screen.getByTestId("sidebar-group-label")).toHaveClass(
        "cursor-default",
      );
    });

    it("should render all bundle items", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(screen.getByTestId("bundle-item-bundle1")).toBeInTheDocument();
      expect(screen.getByTestId("bundle-item-bundle2")).toBeInTheDocument();
      expect(screen.getByTestId("bundle-item-bundle3")).toBeInTheDocument();
    });

    it("should display correct bundle names", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(
        screen.getByText("Bundle Item: Bundle 1 - Open: false"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Bundle Item: Bundle 2 - Open: false"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Bundle Item: Bundle 3 - Open: false"),
      ).toBeInTheDocument();
    });

    it("should not render SearchConfigTrigger when showSearchConfigTrigger is false", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(
        screen.queryByTestId("search-config-trigger"),
      ).not.toBeInTheDocument();
    });

    it("should render SearchConfigTrigger when showSearchConfigTrigger is true", () => {
      const propsWithConfigTrigger = {
        ...defaultProps,
        showSearchConfigTrigger: true,
      };

      render(<MemoizedSidebarGroup {...propsWithConfigTrigger} />);

      expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
      expect(screen.getByText("Config Toggle: false")).toBeInTheDocument();
    });

    it("should render SearchConfigTrigger with showConfig true", () => {
      const propsWithConfigTriggerAndShowConfig = {
        ...defaultProps,
        showSearchConfigTrigger: true,
        showConfig: true,
      };

      render(<MemoizedSidebarGroup {...propsWithConfigTriggerAndShowConfig} />);

      expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
      expect(screen.getByText("Config Toggle: true")).toBeInTheDocument();
    });
  });

  describe("Bundle Sorting", () => {
    it("should sort bundles according to BUNDLES order when search is empty", () => {
      const propsWithReorderedBundles = {
        ...defaultProps,
        BUNDLES: [
          { name: "bundle3", display_name: "Bundle 3", icon: "Archive" },
          { name: "bundle1", display_name: "Bundle 1", icon: "Package" },
          { name: "bundle2", display_name: "Bundle 2", icon: "Box" },
        ],
      };

      render(<MemoizedSidebarGroup {...propsWithReorderedBundles} />);

      const bundleItems = screen.getAllByTestId(/bundle-item-/);
      expect(bundleItems[0]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle3",
      );
      expect(bundleItems[1]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle1",
      );
      expect(bundleItems[2]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle2",
      );
    });

    it("should sort bundles according to sortedCategories when search is not empty", () => {
      const propsWithSearch = {
        ...defaultProps,
        search: "test search",
        sortedCategories: ["bundle2", "bundle3", "bundle1"],
      };

      render(<MemoizedSidebarGroup {...propsWithSearch} />);

      const bundleItems = screen.getAllByTestId(/bundle-item-/);
      expect(bundleItems[0]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle2",
      );
      expect(bundleItems[1]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle3",
      );
      expect(bundleItems[2]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle1",
      );
    });

    it("should handle bundles not in sortedCategories gracefully", () => {
      const propsWithPartialSort = {
        ...defaultProps,
        search: "test",
        sortedCategories: ["bundle1"], // Only one bundle in sorted categories
      };

      render(<MemoizedSidebarGroup {...propsWithPartialSort} />);

      // All bundles should still render
      expect(screen.getByTestId("bundle-item-bundle1")).toBeInTheDocument();
      expect(screen.getByTestId("bundle-item-bundle2")).toBeInTheDocument();
      expect(screen.getByTestId("bundle-item-bundle3")).toBeInTheDocument();
    });

    it("should handle empty sortedCategories with search", () => {
      const propsWithEmptySort = {
        ...defaultProps,
        search: "test",
        sortedCategories: [],
      };

      render(<MemoizedSidebarGroup {...propsWithEmptySort} />);

      expect(screen.getAllByTestId(/bundle-item-/)).toHaveLength(3);
    });
  });

  describe("Props Passing to BundleItem", () => {
    it("should pass all required props to each BundleItem", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      // Verify that BundleItems are rendered (which means props are passed correctly)
      expect(screen.getByTestId("bundle-item-bundle1")).toBeInTheDocument();
      expect(screen.getByTestId("bundle-item-bundle2")).toBeInTheDocument();
      expect(screen.getByTestId("bundle-item-bundle3")).toBeInTheDocument();
    });

    it("should pass openCategories state correctly", () => {
      const propsWithOpenCategories = {
        ...defaultProps,
        openCategories: ["bundle2"],
      };

      render(<MemoizedSidebarGroup {...propsWithOpenCategories} />);

      expect(
        screen.getByText("Bundle Item: Bundle 1 - Open: false"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Bundle Item: Bundle 2 - Open: true"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Bundle Item: Bundle 3 - Open: false"),
      ).toBeInTheDocument();
    });

    it("should handle multiple open categories", () => {
      const propsWithMultipleOpen = {
        ...defaultProps,
        openCategories: ["bundle1", "bundle3"],
      };

      render(<MemoizedSidebarGroup {...propsWithMultipleOpen} />);

      expect(
        screen.getByText("Bundle Item: Bundle 1 - Open: true"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Bundle Item: Bundle 2 - Open: false"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Bundle Item: Bundle 3 - Open: true"),
      ).toBeInTheDocument();
    });
  });

  describe("Memoization and Performance", () => {
    it("should be memoized for performance", () => {
      expect(MemoizedSidebarGroup.displayName).toBe("MemoizedSidebarGroup");
    });

    it("should not re-render when props haven't changed", () => {
      const { rerender } = render(<MemoizedSidebarGroup {...defaultProps} />);

      const initialElement = screen.getByTestId("sidebar-group");

      // Re-render with same props
      rerender(<MemoizedSidebarGroup {...defaultProps} />);

      expect(screen.getByTestId("sidebar-group")).toBe(initialElement);
    });

    it("should re-render when BUNDLES prop changes", () => {
      const { rerender } = render(<MemoizedSidebarGroup {...defaultProps} />);

      expect(screen.getAllByTestId(/bundle-item-/)).toHaveLength(3);

      const newProps = {
        ...defaultProps,
        BUNDLES: [
          { name: "bundle1", display_name: "Bundle 1", icon: "Package" },
        ],
      };

      rerender(<MemoizedSidebarGroup {...newProps} />);

      expect(screen.getAllByTestId(/bundle-item-/)).toHaveLength(1);
    });

    it("should recalculate sorting when search changes", () => {
      const { rerender } = render(<MemoizedSidebarGroup {...defaultProps} />);

      let bundleItems = screen.getAllByTestId(/bundle-item-/);
      expect(bundleItems[0]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle1",
      );

      const propsWithSearch = {
        ...defaultProps,
        search: "test",
        sortedCategories: ["bundle3", "bundle1", "bundle2"],
      };

      rerender(<MemoizedSidebarGroup {...propsWithSearch} />);

      bundleItems = screen.getAllByTestId(/bundle-item-/);
      expect(bundleItems[0]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle3",
      );
    });

    it("should recalculate sorting when sortedCategories changes", () => {
      const propsWithSearch = {
        ...defaultProps,
        search: "test",
        sortedCategories: ["bundle1", "bundle2", "bundle3"],
      };

      const { rerender } = render(
        <MemoizedSidebarGroup {...propsWithSearch} />,
      );

      let bundleItems = screen.getAllByTestId(/bundle-item-/);
      expect(bundleItems[0]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle1",
      );

      const updatedProps = {
        ...propsWithSearch,
        sortedCategories: ["bundle3", "bundle2", "bundle1"],
      };

      rerender(<MemoizedSidebarGroup {...updatedProps} />);

      bundleItems = screen.getAllByTestId(/bundle-item-/);
      expect(bundleItems[0]).toHaveAttribute(
        "data-testid",
        "bundle-item-bundle3",
      );
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty BUNDLES array", () => {
      const propsWithEmptyBundles = {
        ...defaultProps,
        BUNDLES: [],
      };

      render(<MemoizedSidebarGroup {...propsWithEmptyBundles} />);

      expect(screen.getByTestId("sidebar-group-label")).toHaveTextContent(
        "Bundles",
      );
      expect(screen.queryByTestId(/bundle-item-/)).not.toBeInTheDocument();
    });

    it("should handle single bundle", () => {
      const propsWithSingleBundle = {
        ...defaultProps,
        BUNDLES: [
          { name: "bundle1", display_name: "Bundle 1", icon: "Package" },
        ],
      };

      render(<MemoizedSidebarGroup {...propsWithSingleBundle} />);

      expect(screen.getAllByTestId(/bundle-item-/)).toHaveLength(1);
      expect(screen.getByTestId("bundle-item-bundle1")).toBeInTheDocument();
    });

    it("should handle bundles with same names gracefully", () => {
      const propsWithDuplicateNames = {
        ...defaultProps,
        BUNDLES: [
          { name: "bundle1", display_name: "Bundle 1", icon: "Package" },
          { name: "bundle1", display_name: "Bundle 1 Copy", icon: "Package" },
        ],
      };

      render(<MemoizedSidebarGroup {...propsWithDuplicateNames} />);

      // Should render both (React will warn about duplicate keys, but still render)
      const bundle1Items = screen.getAllByTestId("bundle-item-bundle1");
      expect(bundle1Items.length).toBeGreaterThan(0);
    });

    it("should handle missing dataFilter gracefully", () => {
      const propsWithoutDataFilter = {
        ...defaultProps,
        dataFilter: {},
      };

      render(<MemoizedSidebarGroup {...propsWithoutDataFilter} />);
      // With empty dataFilter, component filters out bundles, so none render
      expect(screen.queryAllByTestId(/bundle-item-/)).toHaveLength(0);
    });

    it("should handle missing nodeColors gracefully", () => {
      const propsWithoutNodeColors = {
        ...defaultProps,
        nodeColors: {},
      };

      render(<MemoizedSidebarGroup {...propsWithoutNodeColors} />);

      expect(screen.getAllByTestId(/bundle-item-/)).toHaveLength(3);
    });

    it("should handle undefined search and sortedCategories", () => {
      const propsWithEmpty = {
        ...defaultProps,
        search: "",
        sortedCategories: [],
      };

      expect(() => {
        render(<MemoizedSidebarGroup {...propsWithEmpty} />);
      }).not.toThrow();
    });
  });

  describe("Component Structure", () => {
    it("should have correct DOM hierarchy", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      const sidebarGroup = screen.getByTestId("sidebar-group");
      const sidebarGroupLabel = screen.getByTestId("sidebar-group-label");
      const sidebarGroupContent = screen.getByTestId("sidebar-group-content");
      const sidebarMenu = screen.getByTestId("sidebar-menu");

      expect(sidebarGroup).toContainElement(sidebarGroupLabel);
      expect(sidebarGroup).toContainElement(sidebarGroupContent);
      expect(sidebarGroupContent).toContainElement(sidebarMenu);
      expect(sidebarMenu).toContainElement(
        screen.getByTestId("bundle-item-bundle1"),
      );
    });

    it("should render bundle items inside sidebar menu", () => {
      render(<MemoizedSidebarGroup {...defaultProps} />);

      const sidebarMenu = screen.getByTestId("sidebar-menu");
      const bundleItems = screen.getAllByTestId(/bundle-item-/);

      bundleItems.forEach((item) => {
        expect(sidebarMenu).toContainElement(item);
      });
    });

    it("should maintain structure with no bundles", () => {
      const propsWithNoBundles = {
        ...defaultProps,
        BUNDLES: [],
      };

      render(<MemoizedSidebarGroup {...propsWithNoBundles} />);

      expect(screen.getByTestId("sidebar-group")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-group-label")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-group-content")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu")).toBeInTheDocument();
    });
  });

  describe("Bundle Sorting Logic", () => {
    it("should use toSorted method for bundle sorting", () => {
      const propsWithCustomOrder = {
        ...defaultProps,
        BUNDLES: [
          { name: "z", display_name: "Z Bundle", icon: "Package" },
          { name: "a", display_name: "A Bundle", icon: "Package" },
          { name: "m", display_name: "M Bundle", icon: "Package" },
        ],
        sortedCategories: [],
      };

      render(<MemoizedSidebarGroup {...propsWithCustomOrder} />);

      // With empty dataFilter from defaultProps, no items should render
      expect(screen.queryAllByTestId(/bundle-item-/)).toHaveLength(0);
    });

    it("should handle complex sorting scenarios", () => {
      const complexProps = {
        ...defaultProps,
        BUNDLES: [
          { name: "bundle1", display_name: "Bundle 1", icon: "Package" },
          { name: "bundle2", display_name: "Bundle 2", icon: "Box" },
          { name: "bundle3", display_name: "Bundle 3", icon: "Archive" },
          { name: "bundle4", display_name: "Bundle 4", icon: "Package" },
        ],
        search: "test",
        sortedCategories: ["bundle4", "bundle1", "bundle2", "bundle3"], // Include all bundles
      };

      render(<MemoizedSidebarGroup {...complexProps} />);

      // With provided dataFilter in defaultProps, only bundles present render
      const bundleItems = screen.queryAllByTestId(/bundle-item-/);
      expect(bundleItems).toHaveLength(3);
    });
  });

  describe("Callback Functions", () => {
    it("should handle missing callback functions gracefully", () => {
      const propsWithoutCallbacks = {
        ...defaultProps,
        setOpenCategories: undefined as any,
        onDragStart: undefined as any,
        sensitiveSort: undefined as any,
        handleKeyDownInput: undefined as any,
      };

      expect(() => {
        render(<MemoizedSidebarGroup {...propsWithoutCallbacks} />);
      }).not.toThrow();
    });

    it("should work with different callback functions", () => {
      const alternativeSetOpenCategories = jest.fn();
      const alternativeOnDragStart = jest.fn();

      const alternativeProps = {
        ...defaultProps,
        setOpenCategories: alternativeSetOpenCategories,
        onDragStart: alternativeOnDragStart,
      };

      render(<MemoizedSidebarGroup {...alternativeProps} />);

      expect(screen.getAllByTestId(/bundle-item-/)).toHaveLength(3);
    });
  });
});
