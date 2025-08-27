import { render, screen } from "@testing-library/react";
import mockAPIData from "@/utils/testUtils/mockData/mockAPIData";
import { SidebarHeaderComponentProps } from "../../types";
import { SidebarHeaderComponent } from "../sidebarHeader";

// Mock the UI components
jest.mock("@/components/ui/disclosure", () => ({
  Disclosure: ({ children, open, onOpenChange }: any) => (
    <div
      data-testid="disclosure"
      data-open={open}
      data-on-open-change={onOpenChange?.toString()}
    >
      {children}
    </div>
  ),
  DisclosureContent: ({ children }: any) => (
    <div data-testid="disclosure-content">{children}</div>
  ),
  DisclosureTrigger: ({ children }: any) => (
    <div data-testid="disclosure-trigger">{children}</div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, variant, size, className, ...props }: any) => (
    <button
      onClick={onClick}
      className={className}
      data-variant={variant}
      data-size={size}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name, className }: any) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
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

jest.mock("@/components/ui/sidebar", () => ({
  SidebarHeader: ({ children, className }: any) => (
    <div data-testid="sidebar-header" className={className}>
      {children}
    </div>
  ),
  SidebarTrigger: ({ children, className }: any) => (
    <div data-testid="sidebar-trigger" className={className}>
      {children}
    </div>
  ),
}));

jest.mock("../featureTogglesComponent", () => ({
  __esModule: true,
  default: ({ showBeta, setShowBeta, showLegacy, setShowLegacy }: any) => (
    <div
      data-testid="feature-toggles"
      data-show-beta={showBeta}
      data-show-legacy={showLegacy}
      data-set-show-beta={setShowBeta?.toString()}
      data-set-show-legacy={setShowLegacy?.toString()}
    >
      Feature Toggles
    </div>
  ),
}));

jest.mock("../searchInput", () => ({
  SearchInput: ({
    searchInputRef,
    isInputFocused,
    search,
    handleInputFocus,
    handleInputBlur,
    handleInputChange,
  }: any) => (
    <div
      data-testid="search-input"
      data-is-focused={isInputFocused}
      data-search={search}
      data-handle-focus={handleInputFocus?.toString()}
      data-handle-blur={handleInputBlur?.toString()}
      data-handle-change={handleInputChange?.toString()}
    >
      Search Input
    </div>
  ),
}));

jest.mock("../sidebarFilterComponent", () => ({
  SidebarFilterComponent: ({ isInput, type, color, resetFilters }: any) => (
    <div
      data-testid="sidebar-filter"
      data-is-input={isInput}
      data-type={type}
      data-color={color}
      data-reset-filters={resetFilters?.toString()}
    >
      Sidebar Filter
    </div>
  ),
}));

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: false, // Default to old sidebar for most tests
}));

describe("SidebarHeaderComponent", () => {
  const mockSetShowConfig = jest.fn();
  const mockSetShowBeta = jest.fn();
  const mockSetShowLegacy = jest.fn();
  const mockHandleInputFocus = jest.fn();
  const mockHandleInputBlur = jest.fn();
  const mockHandleInputChange = jest.fn();
  const mockSetFilterEdge = jest.fn();
  const mockSetFilterData = jest.fn();

  const defaultProps: SidebarHeaderComponentProps = {
    showConfig: false,
    setShowConfig: mockSetShowConfig,
    showBeta: false,
    setShowBeta: mockSetShowBeta,
    showLegacy: false,
    setShowLegacy: mockSetShowLegacy,
    searchInputRef: { current: null },
    isInputFocused: false,
    search: "",
    handleInputFocus: mockHandleInputFocus,
    handleInputBlur: mockHandleInputBlur,
    handleInputChange: mockHandleInputChange,
    filterType: undefined,
    setFilterEdge: mockSetFilterEdge,
    setFilterData: mockSetFilterData,
    data: mockAPIData,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    describe("Legacy Sidebar (!ENABLE_NEW_SIDEBAR)", () => {
      it("should render sidebar header with legacy structure", () => {
        render(<SidebarHeaderComponent {...defaultProps} />);

        expect(screen.getByTestId("sidebar-header")).toBeInTheDocument();
        expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
        expect(screen.getByText("Components")).toBeInTheDocument();
        expect(
          screen.getByTestId("sidebar-options-trigger"),
        ).toBeInTheDocument();
        expect(screen.getByTestId("disclosure-trigger")).toBeInTheDocument();
        expect(screen.getByTestId("search-input")).toBeInTheDocument();
        expect(screen.getByTestId("disclosure")).toBeInTheDocument();
        expect(screen.getByTestId("disclosure-content")).toBeInTheDocument();
        expect(screen.getByTestId("feature-toggles")).toBeInTheDocument();
      });

      it("should render sidebar trigger with correct icon", () => {
        render(<SidebarHeaderComponent {...defaultProps} />);

        expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
        expect(screen.getByTestId("icon-PanelLeftClose")).toBeInTheDocument();
      });

      it("should render settings button with correct props", () => {
        render(<SidebarHeaderComponent {...defaultProps} />);

        const settingsButton = screen.getByTestId("sidebar-options-trigger");
        expect(settingsButton).toHaveAttribute("data-variant", "ghost");
        expect(settingsButton).toHaveAttribute("data-size", "iconMd");
        expect(
          screen.getByTestId("icon-SlidersHorizontal"),
        ).toBeInTheDocument();
      });

      it("should show ghostActive variant when config is open", () => {
        const propsWithOpenConfig = { ...defaultProps, showConfig: true };
        render(<SidebarHeaderComponent {...propsWithOpenConfig} />);

        const settingsButton = screen.getByTestId("sidebar-options-trigger");
        expect(settingsButton).toHaveAttribute("data-variant", "ghostActive");
      });

      it("should render tooltip with correct content", () => {
        render(<SidebarHeaderComponent {...defaultProps} />);

        expect(screen.getByTestId("tooltip")).toHaveAttribute(
          "data-content",
          "Component settings",
        );
        expect(screen.getByTestId("tooltip")).toHaveClass("z-50");
      });
    });

    it("should apply correct CSS classes to header", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const header = screen.getByTestId("sidebar-header");
      expect(header).toHaveClass(
        "flex",
        "w-full",
        "flex-col",
        "gap-2",
        "p-4",
        "pb-1",
        "group-data-[collapsible=icon]:hidden",
      );
    });

    it("should render search input component with correct props", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const searchInput = screen.getByTestId("search-input");
      expect(searchInput).toBeInTheDocument();
      expect(searchInput).toHaveAttribute("data-search", "");
      expect(searchInput).toHaveAttribute("data-is-focused", "false");
    });
  });

  describe("Disclosure Functionality", () => {
    it("should render disclosure with correct closed state", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toBeInTheDocument();
      expect(disclosure).toHaveAttribute("data-open", "false");
    });

    it("should render disclosure as open when showConfig is true", () => {
      const propsWithOpenConfig = {
        ...defaultProps,
        showConfig: true,
      };

      render(<SidebarHeaderComponent {...propsWithOpenConfig} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "true");
    });

    it("should pass setShowConfig to disclosure", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute(
        "data-on-open-change",
        mockSetShowConfig.toString(),
      );
    });

    it("should render disclosure content", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("disclosure-content")).toBeInTheDocument();
    });

    it("should contain feature toggles within disclosure content", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const disclosureContent = screen.getByTestId("disclosure-content");
      const featureToggles = screen.getByTestId("feature-toggles");

      expect(disclosureContent).toContainElement(featureToggles);
    });
  });

  describe("Feature Toggles Integration", () => {
    it("should render feature toggles with correct props", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const featureToggles = screen.getByTestId("feature-toggles");
      expect(featureToggles).toHaveAttribute("data-show-beta", "false");
      expect(featureToggles).toHaveAttribute("data-show-legacy", "false");
      expect(featureToggles).toHaveAttribute(
        "data-set-show-beta",
        mockSetShowBeta.toString(),
      );
      expect(featureToggles).toHaveAttribute(
        "data-set-show-legacy",
        mockSetShowLegacy.toString(),
      );
    });

    it("should pass different beta and legacy values", () => {
      const propsWithToggles = {
        ...defaultProps,
        showBeta: true,
        showLegacy: true,
      };

      render(<SidebarHeaderComponent {...propsWithToggles} />);

      const featureToggles = screen.getByTestId("feature-toggles");
      expect(featureToggles).toHaveAttribute("data-show-beta", "true");
      expect(featureToggles).toHaveAttribute("data-show-legacy", "true");
    });
  });

  describe("Search Input Integration", () => {
    it("should render search input with correct props", () => {
      const propsWithSearch = {
        ...defaultProps,
        search: "test search",
        isInputFocused: true,
      };

      render(<SidebarHeaderComponent {...propsWithSearch} />);

      const searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-search", "test search");
      expect(searchInput).toHaveAttribute("data-is-focused", "true");
    });

    it("should pass search input ref and callbacks", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute(
        "data-handle-focus",
        mockHandleInputFocus.toString(),
      );
      expect(searchInput).toHaveAttribute(
        "data-handle-blur",
        mockHandleInputBlur.toString(),
      );
      expect(searchInput).toHaveAttribute(
        "data-handle-change",
        mockHandleInputChange.toString(),
      );
    });
  });

  describe("Filter Component Conditional Rendering", () => {
    it("should not render filter component when filterType is null", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.queryByTestId("sidebar-filter")).not.toBeInTheDocument();
    });

    it("should render filter component when filterType is provided", () => {
      const propsWithFilter = {
        ...defaultProps,
        filterType: {
          source: "input",
          sourceHandle: "input",
          target: undefined,
          targetHandle: undefined,
          type: "input",
          color: "#FF0000",
        },
      };

      render(<SidebarHeaderComponent {...propsWithFilter} />);

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toBeInTheDocument();
      expect(filterComponent).toHaveAttribute("data-is-input", "true");
      expect(filterComponent).toHaveAttribute("data-type", "input");
      expect(filterComponent).toHaveAttribute("data-color", "#FF0000");
    });

    it("should pass correct props to filter component for output", () => {
      const propsWithOutputFilter = {
        ...defaultProps,
        filterType: {
          source: undefined,
          sourceHandle: undefined,
          target: "output",
          targetHandle: "output",
          type: "output",
          color: "#00FF00",
        },
      };

      render(<SidebarHeaderComponent {...propsWithOutputFilter} />);

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toHaveAttribute("data-is-input", "false");
      expect(filterComponent).toHaveAttribute("data-type", "output");
      expect(filterComponent).toHaveAttribute("data-color", "#00FF00");
    });

    it("should handle filter reset correctly", () => {
      const propsWithFilter = {
        ...defaultProps,
        filterType: {
          source: "input",
          sourceHandle: "input",
          target: "output",
          targetHandle: "output",
          type: "input",
          color: "#FF0000",
        },
      };

      render(<SidebarHeaderComponent {...propsWithFilter} />);

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toHaveAttribute(
        "data-reset-filters",
        expect.stringContaining("function"),
      );
    });
  });

  describe("Component Structure", () => {
    it("should have correct DOM hierarchy", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const header = screen.getByTestId("sidebar-header");
      const searchInput = screen.getByTestId("search-input");
      const disclosure = screen.getByTestId("disclosure");
      const disclosureContent = screen.getByTestId("disclosure-content");
      const featureToggles = screen.getByTestId("feature-toggles");

      expect(header).toContainElement(searchInput);
      expect(header).toContainElement(disclosure);
      expect(disclosure).toContainElement(disclosureContent);
      expect(disclosureContent).toContainElement(featureToggles);
    });

    it("should maintain structure with filter component", () => {
      const propsWithFilter = {
        ...defaultProps,
        filterType: {
          source: "input",
          sourceHandle: "input",
          target: "output",
          targetHandle: "output",
          type: "input",
          color: "#FF0000",
        },
      };

      render(<SidebarHeaderComponent {...propsWithFilter} />);

      const header = screen.getByTestId("sidebar-header");
      const searchInput = screen.getByTestId("search-input");
      const filterComponent = screen.getByTestId("sidebar-filter");
      const disclosure = screen.getByTestId("disclosure");

      expect(header).toContainElement(searchInput);
      expect(header).toContainElement(filterComponent);
      expect(header).toContainElement(disclosure);
    });
  });

  describe("Props Handling", () => {
    it("should handle different showConfig values", () => {
      const { rerender } = render(<SidebarHeaderComponent {...defaultProps} />);

      let disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "false");

      rerender(<SidebarHeaderComponent {...defaultProps} showConfig={true} />);
      disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "true");
    });

    it("should handle different search values", () => {
      const { rerender } = render(<SidebarHeaderComponent {...defaultProps} />);

      let searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-search", "");

      rerender(
        <SidebarHeaderComponent {...defaultProps} search="new search" />,
      );
      searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-search", "new search");
    });

    it("should handle different callback functions", () => {
      const alternativeSetShowConfig = jest.fn();
      const alternativeProps = {
        ...defaultProps,
        setShowConfig: alternativeSetShowConfig,
      };

      render(<SidebarHeaderComponent {...alternativeProps} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute(
        "data-on-open-change",
        alternativeSetShowConfig.toString(),
      );
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing callback functions gracefully", () => {
      const propsWithoutCallbacks = {
        ...defaultProps,
        setShowConfig: undefined as any,
        setShowBeta: undefined as any,
        setShowLegacy: undefined as any,
        handleInputFocus: undefined as any,
        handleInputBlur: undefined as any,
        handleInputChange: undefined as any,
      };

      expect(() => {
        render(<SidebarHeaderComponent {...propsWithoutCallbacks} />);
      }).not.toThrow();
    });

    it("should handle undefined filterType gracefully", () => {
      const propsWithUndefinedFilter = {
        ...defaultProps,
        filterType: undefined,
      };

      render(<SidebarHeaderComponent {...propsWithUndefinedFilter} />);
      expect(screen.queryByTestId("sidebar-filter")).not.toBeInTheDocument();
    });

    it("should handle complex filterType objects", () => {
      const propsWithComplexFilter = {
        ...defaultProps,
        filterType: {
          source: "input",
          sourceHandle: "input",
          target: undefined,
          targetHandle: undefined,
          type: "complex-input",
          color: "#ABCDEF",
          additionalProp: "ignored",
        },
      };

      expect(() => {
        render(<SidebarHeaderComponent {...propsWithComplexFilter} />);
      }).not.toThrow();

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toBeInTheDocument();
    });
  });

  describe("Memo Functionality", () => {
    it("should render component name correctly", () => {
      expect(SidebarHeaderComponent.displayName).toBe("SidebarHeaderComponent");
    });

    it("should handle prop changes correctly", () => {
      const { rerender } = render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("sidebar-header")).toBeInTheDocument();

      const newProps = { ...defaultProps, search: "updated search" };
      rerender(<SidebarHeaderComponent {...newProps} />);

      const searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-search", "updated search");
    });
  });

  describe("Integration", () => {
    it("should integrate all child components correctly", () => {
      const fullProps = {
        ...defaultProps,
        search: "integration test",
        showConfig: true,
        showBeta: true,
        showLegacy: false,
        isInputFocused: true,
        filterType: {
          source: "input",
          sourceHandle: "input",
          target: undefined,
          targetHandle: undefined,
          type: "input",
          color: "#123456",
        },
      };

      render(<SidebarHeaderComponent {...fullProps} />);

      // Verify all components are integrated correctly
      expect(screen.getByTestId("sidebar-header")).toBeInTheDocument();
      expect(screen.getByTestId("search-input")).toHaveAttribute(
        "data-search",
        "integration test",
      );
      expect(screen.getByTestId("sidebar-filter")).toHaveAttribute(
        "data-type",
        "input",
      );
      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "true",
      );
      expect(screen.getByTestId("feature-toggles")).toHaveAttribute(
        "data-show-beta",
        "true",
      );
    });
  });
});
