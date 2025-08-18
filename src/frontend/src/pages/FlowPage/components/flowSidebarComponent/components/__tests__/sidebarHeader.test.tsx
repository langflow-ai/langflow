import { render, screen } from "@testing-library/react";
import mockAPIData from "@/utils/testUtils/mockData/mockAPIData";
import { SidebarHeaderComponentProps } from "../../types";
import { SidebarHeaderComponent } from "../sidebarHeader";

// Mock the UI components
jest.mock("@/components/common/genericIconComponent", () => ({
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
      Filter Component
    </div>
  ),
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
  const mockSearchInputRef = { current: null };

  const defaultProps: SidebarHeaderComponentProps = {
    showConfig: false,
    setShowConfig: mockSetShowConfig,
    showBeta: false,
    setShowBeta: mockSetShowBeta,
    showLegacy: false,
    setShowLegacy: mockSetShowLegacy,
    searchInputRef: mockSearchInputRef,
    isInputFocused: false,
    search: "",
    handleInputFocus: mockHandleInputFocus,
    handleInputBlur: mockHandleInputBlur,
    handleInputChange: mockHandleInputChange,
    filterType: undefined,
    setFilterEdge: mockSetFilterEdge,
    setFilterData: mockSetFilterData,
    data: {},
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render sidebar header with correct structure", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("sidebar-header")).toBeInTheDocument();
      expect(screen.getByTestId("disclosure")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
      expect(screen.getByText("Components")).toBeInTheDocument();
      expect(screen.getByTestId("search-input")).toBeInTheDocument();
    });

    it("should display correct title", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByText("Components")).toBeInTheDocument();
    });

    it("should render sidebar trigger with icon", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
      expect(
        screen.getByTestId("forwarded-icon-PanelLeftClose"),
      ).toBeInTheDocument();
    });

    it("should render settings button", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("sidebar-options-trigger")).toBeInTheDocument();
      expect(
        screen.getByTestId("forwarded-icon-SlidersHorizontal"),
      ).toBeInTheDocument();
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

  describe("Disclosure Functionality", () => {
    it("should render disclosure with correct open state", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "false",
      );
    });

    it("should render disclosure as open when showConfig is true", () => {
      const propsWithOpenConfig = { ...defaultProps, showConfig: true };
      render(<SidebarHeaderComponent {...propsWithOpenConfig} />);

      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "true",
      );
    });

    it("should pass setShowConfig to disclosure", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-on-open-change",
        mockSetShowConfig.toString(),
      );
    });

    it("should render disclosure content", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("disclosure-content")).toBeInTheDocument();
    });

    it("should render disclosure trigger", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("disclosure-trigger")).toBeInTheDocument();
    });
  });

  describe("Settings Button Variants", () => {
    it("should show ghost variant when config is closed", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const settingsButton = screen.getByTestId("sidebar-options-trigger");
      expect(settingsButton).toHaveAttribute("data-variant", "ghost");
    });

    it("should show ghostActive variant when config is open", () => {
      const propsWithOpenConfig = { ...defaultProps, showConfig: true };
      render(<SidebarHeaderComponent {...propsWithOpenConfig} />);

      const settingsButton = screen.getByTestId("sidebar-options-trigger");
      expect(settingsButton).toHaveAttribute("data-variant", "ghostActive");
    });

    it("should have correct size", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const settingsButton = screen.getByTestId("sidebar-options-trigger");
      expect(settingsButton).toHaveAttribute("data-size", "iconMd");
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
        isInputFocused: true,
        search: "test search",
      };

      render(<SidebarHeaderComponent {...propsWithSearch} />);

      const searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-is-focused", "true");
      expect(searchInput).toHaveAttribute("data-search", "test search");
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

    it("should pass search input ref", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("search-input")).toBeInTheDocument();
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
          source: "test_source",
          sourceHandle: undefined,
          target: undefined,
          targetHandle: undefined,
          type: "string",
          color: "blue",
        },
      };

      render(<SidebarHeaderComponent {...propsWithFilter} />);

      expect(screen.getByTestId("sidebar-filter")).toBeInTheDocument();
    });

    it("should pass correct props to filter component for input", () => {
      const propsWithInputFilter = {
        ...defaultProps,
        filterType: {
          source: "test_source",
          sourceHandle: undefined,
          target: undefined,
          targetHandle: undefined,
          type: "string",
          color: "blue",
        },
      };

      render(<SidebarHeaderComponent {...propsWithInputFilter} />);

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toHaveAttribute("data-is-input", "true");
      expect(filterComponent).toHaveAttribute("data-type", "string");
      expect(filterComponent).toHaveAttribute("data-color", "blue");
    });

    it("should pass correct props to filter component for output", () => {
      const propsWithOutputFilter = {
        ...defaultProps,
        filterType: {
          source: undefined,
          sourceHandle: undefined,
          target: "test_target",
          targetHandle: undefined,
          type: "number",
          color: "red",
        },
      };

      render(<SidebarHeaderComponent {...propsWithOutputFilter} />);

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toHaveAttribute("data-is-input", "false");
      expect(filterComponent).toHaveAttribute("data-type", "number");
      expect(filterComponent).toHaveAttribute("data-color", "red");
    });

    it("should handle filter reset correctly", async () => {
      const propsWithFilter = {
        ...defaultProps,
        filterType: {
          source: "test_source",
          sourceHandle: undefined,
          target: undefined,
          targetHandle: undefined,
          type: "string",
          color: "blue",
        },
        data: mockAPIData,
      };

      render(<SidebarHeaderComponent {...propsWithFilter} />);

      // Since resetFilters is passed as a function, we can't directly test it
      // but we can verify the filter component receives the function
      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toHaveAttribute("data-reset-filters");
    });
  });

  describe("Component Structure", () => {
    it("should have correct DOM hierarchy", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const sidebarHeader = screen.getByTestId("sidebar-header");
      const disclosure = screen.getByTestId("disclosure");
      const searchInput = screen.getByTestId("search-input");

      expect(sidebarHeader).toContainElement(disclosure);
      expect(sidebarHeader).toContainElement(searchInput);
    });

    it("should apply correct CSS classes", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const sidebarHeader = screen.getByTestId("sidebar-header");
      expect(sidebarHeader).toHaveClass(
        "flex",
        "w-full",
        "flex-col",
        "gap-4",
        "p-4",
        "pb-1",
      );
    });

    it("should contain all expected child elements", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
      expect(screen.getByText("Components")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-options-trigger")).toBeInTheDocument();
      expect(screen.getByTestId("feature-toggles")).toBeInTheDocument();
      expect(screen.getByTestId("search-input")).toBeInTheDocument();
    });
  });

  describe("CSS Classes", () => {
    it("should apply correct classes to sidebar trigger", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const sidebarTrigger = screen.getByTestId("sidebar-trigger");
      expect(sidebarTrigger).toHaveClass("text-muted-foreground");
    });

    it("should apply correct classes to title", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const title = screen.getByText("Components");
      expect(title).toHaveClass(
        "flex-1",
        "cursor-default",
        "text-sm",
        "font-semibold",
      );
    });

    it("should apply correct classes to settings icon", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const settingsIcon = screen.getByTestId(
        "forwarded-icon-SlidersHorizontal",
      );
      expect(settingsIcon).toHaveClass("h-4", "w-4");
    });
  });

  describe("Props Handling", () => {
    it("should handle different showConfig values", () => {
      const { rerender } = render(
        <SidebarHeaderComponent {...defaultProps} showConfig={false} />,
      );
      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "false",
      );
      expect(screen.getByTestId("sidebar-options-trigger")).toHaveAttribute(
        "data-variant",
        "ghost",
      );

      rerender(<SidebarHeaderComponent {...defaultProps} showConfig={true} />);
      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "true",
      );
      expect(screen.getByTestId("sidebar-options-trigger")).toHaveAttribute(
        "data-variant",
        "ghostActive",
      );
    });

    it("should handle different search values", () => {
      const { rerender } = render(
        <SidebarHeaderComponent
          {...defaultProps}
          search=""
          isInputFocused={false}
        />,
      );
      let searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-search", "");
      expect(searchInput).toHaveAttribute("data-is-focused", "false");

      rerender(
        <SidebarHeaderComponent
          {...defaultProps}
          search="test"
          isInputFocused={true}
        />,
      );
      searchInput = screen.getByTestId("search-input");
      expect(searchInput).toHaveAttribute("data-search", "test");
      expect(searchInput).toHaveAttribute("data-is-focused", "true");
    });

    it("should handle different callback functions", () => {
      const alternativeSetShowConfig = jest.fn();
      const alternativeHandleInputChange = jest.fn();

      render(
        <SidebarHeaderComponent
          {...defaultProps}
          setShowConfig={alternativeSetShowConfig}
          handleInputChange={alternativeHandleInputChange}
        />,
      );

      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-on-open-change",
        alternativeSetShowConfig.toString(),
      );
      expect(screen.getByTestId("search-input")).toHaveAttribute(
        "data-handle-change",
        alternativeHandleInputChange.toString(),
      );
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing callback functions gracefully", () => {
      const propsWithoutCallbacks = {
        ...defaultProps,
        setShowConfig: undefined as any,
        handleInputFocus: undefined as any,
        handleInputBlur: undefined as any,
        handleInputChange: undefined as any,
      };

      expect(() => {
        render(<SidebarHeaderComponent {...propsWithoutCallbacks} />);
      }).not.toThrow();
    });

    it("should handle null filterType gracefully", () => {
      render(
        <SidebarHeaderComponent {...defaultProps} filterType={undefined} />,
      );

      expect(screen.queryByTestId("sidebar-filter")).not.toBeInTheDocument();
    });

    it("should handle undefined filterType gracefully", () => {
      const propsWithUndefinedFilter = {
        ...defaultProps,
        filterType: undefined as any,
      };

      render(<SidebarHeaderComponent {...propsWithUndefinedFilter} />);

      expect(screen.queryByTestId("sidebar-filter")).not.toBeInTheDocument();
    });

    it("should handle complex filterType objects", () => {
      const complexFilterType = {
        source: "test_source",
        sourceHandle: undefined,
        target: undefined,
        targetHandle: undefined,
        type: "List[str, int]",
        color: "custom-color",
        additionalProp: "ignored",
      };

      const propsWithComplexFilter = {
        ...defaultProps,
        filterType: complexFilterType,
      };

      render(<SidebarHeaderComponent {...propsWithComplexFilter} />);

      const filterComponent = screen.getByTestId("sidebar-filter");
      expect(filterComponent).toHaveAttribute("data-type", "List[str, int]");
      expect(filterComponent).toHaveAttribute("data-color", "custom-color");
    });
  });

  describe("Memo Functionality", () => {
    it("should render component name correctly", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      // Component should render without issues
      expect(screen.getByTestId("sidebar-header")).toBeInTheDocument();
    });

    it("should handle prop changes correctly", () => {
      const { rerender } = render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "false",
      );

      rerender(<SidebarHeaderComponent {...defaultProps} showConfig={true} />);

      expect(screen.getByTestId("disclosure")).toHaveAttribute(
        "data-open",
        "true",
      );
    });
  });

  describe("Accessibility", () => {
    it("should have proper heading structure", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      const title = screen.getByText("Components");
      expect(title.tagName).toBe("H3");
    });

    it("should render tooltip for settings button", () => {
      render(<SidebarHeaderComponent {...defaultProps} />);

      expect(screen.getByTestId("tooltip")).toHaveAttribute(
        "data-content",
        "Component settings",
      );
    });
  });

  describe("Integration", () => {
    it("should integrate all child components correctly", () => {
      const propsWithFilter = {
        ...defaultProps,
        showConfig: true,
        showBeta: true,
        showLegacy: true,
        isInputFocused: true,
        search: "test search",
        filterType: {
          source: "test_source",
          sourceHandle: undefined,
          target: undefined,
          targetHandle: undefined,
          type: "string",
          color: "blue",
        },
      };

      render(<SidebarHeaderComponent {...propsWithFilter} />);

      expect(screen.getByTestId("feature-toggles")).toBeInTheDocument();
      expect(screen.getByTestId("search-input")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-filter")).toBeInTheDocument();
    });
  });
});
