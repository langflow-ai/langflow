import { render, screen } from "@testing-library/react";
import React from "react";
import { CategoryGroup } from "../categoryGroup";

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

// Mock the CategoryDisclosure component
jest.mock("../categoryDisclouse", () => ({
  CategoryDisclosure: ({ item, openCategories }: any) => (
    <div data-testid={`category-disclosure-${item.name}`}>
      CategoryDisclosure for {item.display_name} - Open:{" "}
      {openCategories.includes(item.name).toString()}
    </div>
  ),
}));

// Mock styleUtils
jest.mock("@/utils/styleUtils", () => ({
  SIDEBAR_BUNDLES: [
    { name: "bundle1", display_name: "Bundle 1" },
    { name: "bundle2", display_name: "Bundle 2" },
  ],
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

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: true, // Set to true for SearchConfigTrigger tests
}));

describe("CategoryGroup", () => {
  const mockSetOpenCategories = jest.fn();
  const mockOnDragStart = jest.fn();
  const mockSensitiveSort = jest.fn();
  const mockSetShowConfig = jest.fn();

  const mockAPIClass = {
    description: "Test component",
    template: {},
    display_name: "Test Component",
    documentation: "Test docs",
  };

  const defaultProps = {
    dataFilter: {
      category1: {
        component1: { ...mockAPIClass, display_name: "Component 1" },
        component2: { ...mockAPIClass, display_name: "Component 2" },
      },
      category2: {
        component3: { ...mockAPIClass, display_name: "Component 3" },
      },
      bundle1: {
        bundleComponent: { ...mockAPIClass, display_name: "Bundle Component" },
      },
      custom_component: {
        customComp: { ...mockAPIClass, display_name: "Custom Component" },
      },
    },
    sortedCategories: ["category2", "category1"],
    CATEGORIES: [
      { display_name: "Category 1", name: "category1", icon: "Folder" },
      { display_name: "Category 2", name: "category2", icon: "File" },
    ],
    openCategories: [],
    setOpenCategories: mockSetOpenCategories,
    search: "",
    nodeColors: {
      category1: "#FF0000",
      category2: "#00FF00",
    },
    onDragStart: mockOnDragStart,
    sensitiveSort: mockSensitiveSort,
    showConfig: false,
    setShowConfig: mockSetShowConfig,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockSetShowConfig.mockClear();
  });

  describe("Basic Rendering", () => {
    it("should render sidebar group with correct structure", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(screen.getByTestId("sidebar-group")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-group-content")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu")).toBeInTheDocument();
    });

    it("should render CategoryDisclosure for each valid category", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(
        screen.getByTestId("category-disclosure-category1"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("category-disclosure-category2"),
      ).toBeInTheDocument();
    });

    it("should display correct category names", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(
        screen.getByText("CategoryDisclosure for Category 1 - Open: false"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("CategoryDisclosure for Category 2 - Open: false"),
      ).toBeInTheDocument();
    });

    it("should render SearchConfigTrigger with correct props", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
      expect(screen.getByText("Config Toggle: false")).toBeInTheDocument();
    });

    it("should render SearchConfigTrigger with showConfig true", () => {
      const propsWithShowConfig = {
        ...defaultProps,
        showConfig: true,
      };

      render(<CategoryGroup {...propsWithShowConfig} />);

      expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
      expect(screen.getByText("Config Toggle: true")).toBeInTheDocument();
    });
  });

  describe("Category Filtering", () => {
    it("should exclude bundle categories", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(
        screen.queryByTestId("category-disclosure-bundle1"),
      ).not.toBeInTheDocument();
    });

    it("should exclude custom_component category", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(
        screen.queryByTestId("category-disclosure-custom_component"),
      ).not.toBeInTheDocument();
    });

    it("should exclude categories with no items", () => {
      const propsWithEmptyCategory = {
        ...defaultProps,
        dataFilter: {
          ...defaultProps.dataFilter,
          emptyCategory: {},
        },
        CATEGORIES: [
          ...defaultProps.CATEGORIES,
          {
            display_name: "Empty Category",
            name: "emptyCategory",
            icon: "Empty",
          },
        ],
      };

      render(<CategoryGroup {...propsWithEmptyCategory} />);

      expect(
        screen.queryByTestId("category-disclosure-emptyCategory"),
      ).not.toBeInTheDocument();
    });

    it("should include categories with items", () => {
      render(<CategoryGroup {...defaultProps} />);

      expect(
        screen.getByTestId("category-disclosure-category1"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("category-disclosure-category2"),
      ).toBeInTheDocument();
    });
  });

  describe("Category Sorting", () => {
    it("should sort categories according to CATEGORIES order when search is empty", () => {
      const propsWithReorderedCategories = {
        ...defaultProps,
        CATEGORIES: [
          { display_name: "Category 2", name: "category2", icon: "File" },
          { display_name: "Category 1", name: "category1", icon: "Folder" },
        ],
      };

      render(<CategoryGroup {...propsWithReorderedCategories} />);

      const disclosures = screen.getAllByTestId(/category-disclosure-/);
      expect(disclosures[0]).toHaveAttribute(
        "data-testid",
        "category-disclosure-category2",
      );
      expect(disclosures[1]).toHaveAttribute(
        "data-testid",
        "category-disclosure-category1",
      );
    });

    it("should sort categories according to sortedCategories when search is not empty", () => {
      const propsWithSearch = {
        ...defaultProps,
        search: "test search",
        sortedCategories: ["category1", "category2"],
      };

      render(<CategoryGroup {...propsWithSearch} />);

      const disclosures = screen.getAllByTestId(/category-disclosure-/);
      expect(disclosures[0]).toHaveAttribute(
        "data-testid",
        "category-disclosure-category1",
      );
      expect(disclosures[1]).toHaveAttribute(
        "data-testid",
        "category-disclosure-category2",
      );
    });

    it("should handle categories not in CATEGORIES list", () => {
      const propsWithUnknownCategory = {
        ...defaultProps,
        dataFilter: {
          ...defaultProps.dataFilter,
          unknownCategory: {
            unknownComp: { ...mockAPIClass, display_name: "Unknown Component" },
          },
        },
      };

      render(<CategoryGroup {...propsWithUnknownCategory} />);

      expect(
        screen.getByTestId("category-disclosure-unknownCategory"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "CategoryDisclosure for unknownCategory - Open: false",
        ),
      ).toBeInTheDocument();
    });
  });

  describe("Open Categories State", () => {
    it("should pass correct open state to CategoryDisclosure", () => {
      const propsWithOpenCategories = {
        ...defaultProps,
        openCategories: ["category1"],
      };

      render(<CategoryGroup {...propsWithOpenCategories} />);

      expect(
        screen.getByText("CategoryDisclosure for Category 1 - Open: true"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("CategoryDisclosure for Category 2 - Open: false"),
      ).toBeInTheDocument();
    });

    it("should handle multiple open categories", () => {
      const propsWithMultipleOpen = {
        ...defaultProps,
        openCategories: ["category1", "category2"],
      };

      render(<CategoryGroup {...propsWithMultipleOpen} />);

      expect(
        screen.getByText("CategoryDisclosure for Category 1 - Open: true"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("CategoryDisclosure for Category 2 - Open: true"),
      ).toBeInTheDocument();
    });
  });

  describe("Props Passing", () => {
    it("should pass all required props to CategoryDisclosure", () => {
      const { rerender } = render(<CategoryGroup {...defaultProps} />);

      // Verify components are rendered (props are passed correctly)
      expect(
        screen.getByTestId("category-disclosure-category1"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("category-disclosure-category2"),
      ).toBeInTheDocument();

      // Re-render to ensure props are consistent
      rerender(<CategoryGroup {...defaultProps} />);
      expect(
        screen.getByTestId("category-disclosure-category1"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("category-disclosure-category2"),
      ).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should render nothing when no valid categories exist", () => {
      const propsWithNoValidCategories = {
        ...defaultProps,
        dataFilter: {
          bundle1: {
            bundleComp: { ...mockAPIClass, display_name: "Bundle Component" },
          },
          custom_component: {
            customComp: { ...mockAPIClass, display_name: "Custom Component" },
          },
        },
      };

      render(<CategoryGroup {...propsWithNoValidCategories} />);

      expect(
        screen.queryByTestId(/category-disclosure-/),
      ).not.toBeInTheDocument();
    });

    it("should handle empty dataFilter gracefully", () => {
      const propsWithEmptyDataFilter = {
        ...defaultProps,
        dataFilter: {},
      };

      render(<CategoryGroup {...propsWithEmptyDataFilter} />);

      expect(
        screen.queryByTestId(/category-disclosure-/),
      ).not.toBeInTheDocument();
    });

    it("should handle missing CATEGORIES gracefully", () => {
      const propsWithMissingCategories = {
        ...defaultProps,
        CATEGORIES: [],
        dataFilter: {
          randomCategory: {
            comp: { ...mockAPIClass, display_name: "Random Component" },
          },
        },
      };

      render(<CategoryGroup {...propsWithMissingCategories} />);

      expect(
        screen.getByTestId("category-disclosure-randomCategory"),
      ).toBeInTheDocument();
    });
  });

  describe("Memoization", () => {
    it("should be wrapped with memo for performance", () => {
      expect(CategoryGroup.displayName).toBe("CategoryGroup");
    });

    it("should not re-render when props haven't changed", () => {
      const { rerender } = render(<CategoryGroup {...defaultProps} />);

      const initialElement = screen.getByTestId("sidebar-group");

      // Re-render with same props
      rerender(<CategoryGroup {...defaultProps} />);

      expect(screen.getByTestId("sidebar-group")).toBe(initialElement);
    });
  });

  describe("Complex Scenarios", () => {
    it("should handle mixed bundle and category data", () => {
      const complexDataFilter = {
        category1: {
          comp1: { ...mockAPIClass, display_name: "Component 1" },
        },
        bundle1: {
          bundleComp: { ...mockAPIClass, display_name: "Bundle Component" },
        },
        category2: {
          comp2: { ...mockAPIClass, display_name: "Component 2" },
        },
        custom_component: {
          customComp: { ...mockAPIClass, display_name: "Custom Component" },
        },
      };

      const propsWithComplexData = {
        ...defaultProps,
        dataFilter: complexDataFilter,
      };

      render(<CategoryGroup {...propsWithComplexData} />);

      // Should render only categories, not bundles or custom_component
      expect(
        screen.getByTestId("category-disclosure-category1"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("category-disclosure-category2"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("category-disclosure-bundle1"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("category-disclosure-custom_component"),
      ).not.toBeInTheDocument();
    });

    it("should handle search and sorting together", () => {
      const propsWithSearchAndSort = {
        ...defaultProps,
        search: "search term",
        sortedCategories: ["category2", "category1"],
      };

      render(<CategoryGroup {...propsWithSearchAndSort} />);

      const disclosures = screen.getAllByTestId(/category-disclosure-/);
      expect(disclosures).toHaveLength(2);
      // Order should follow sortedCategories when search is present
      expect(disclosures[0]).toHaveAttribute(
        "data-testid",
        "category-disclosure-category2",
      );
      expect(disclosures[1]).toHaveAttribute(
        "data-testid",
        "category-disclosure-category1",
      );
    });
  });
});
