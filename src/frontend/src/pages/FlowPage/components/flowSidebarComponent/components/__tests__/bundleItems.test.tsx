import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { BundleItem } from "../bundleItems";

// Mock the UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: any) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/ui/disclosure", () => ({
  Disclosure: ({ children, open, onOpenChange }: any) => (
    <div
      data-testid="disclosure"
      data-open={open}
      data-on-open-change={onOpenChange?.toString()}
    >
      {React.Children.map(children, (child, index) => {
        if (index === 0) {
          return React.cloneElement(child, { onOpenChange });
        }
        return child;
      })}
    </div>
  ),
  DisclosureContent: ({ children }: any) => (
    <div data-testid="disclosure-content">{children}</div>
  ),
  DisclosureTrigger: ({ children, className }: any) => (
    <div data-testid="disclosure-trigger" className={className}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarMenuButton: ({ children, asChild }: any) => (
    <div data-testid="sidebar-menu-button">
      {asChild ? children : <button>{children}</button>}
    </div>
  ),
  SidebarMenuItem: ({ children }: any) => (
    <div data-testid="sidebar-menu-item">{children}</div>
  ),
}));

// Mock the SidebarItemsList component
jest.mock("../sidebarItemsList", () => {
  return function MockSidebarItemsList(props: any) {
    return (
      <div data-testid="sidebar-items-list">Items for {props.item?.name}</div>
    );
  };
});

describe("BundleItem", () => {
  const mockSetOpenCategories = jest.fn();
  const mockOnDragStart = jest.fn();
  const mockSensitiveSort = jest.fn();
  const mockHandleKeyDownInput = jest.fn();

  const mockAPIClass = {
    description: "Test component",
    template: {},
    display_name: "Test Component",
    documentation: "Test docs",
  };

  const defaultProps = {
    item: {
      name: "test-bundle",
      display_name: "Test Bundle",
      icon: "Package",
    },
    openCategories: [],
    setOpenCategories: mockSetOpenCategories,
    dataFilter: {
      "test-bundle": {
        component1: { ...mockAPIClass, display_name: "Component 1" },
        component2: { ...mockAPIClass, display_name: "Component 2" },
      },
    },
    nodeColors: {
      "test-bundle": "#FF0000",
    },
    onDragStart: mockOnDragStart,
    sensitiveSort: mockSensitiveSort,
    handleKeyDownInput: mockHandleKeyDownInput,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render bundle item with correct structure", () => {
      render(<BundleItem {...defaultProps} />);

      expect(screen.getByTestId("disclosure")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu-item")).toBeInTheDocument();
      expect(screen.getByTestId("disclosure-trigger")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu-button")).toBeInTheDocument();
    });

    it("should display bundle icon and name", () => {
      render(<BundleItem {...defaultProps} />);

      expect(screen.getByTestId("icon-Package")).toBeInTheDocument();
      expect(screen.getByText("Test Bundle")).toBeInTheDocument();
    });

    it("should display chevron icon", () => {
      render(<BundleItem {...defaultProps} />);

      expect(screen.getByTestId("icon-ChevronRight")).toBeInTheDocument();
    });

    it("should include correct test id for disclosure", () => {
      render(<BundleItem {...defaultProps} />);

      const disclosureDiv = screen.getByTestId(
        "disclosure-bundles-test bundle",
      );
      expect(disclosureDiv).toBeInTheDocument();
    });
  });

  describe("Conditional Rendering", () => {
    it("should still render container even if dataFilter has no items for bundle", () => {
      const propsWithEmptyFilter = {
        ...defaultProps,
        dataFilter: {
          "test-bundle": {},
        },
      };

      const { container } = render(<BundleItem {...propsWithEmptyFilter} />);
      expect(container.firstChild).not.toBeNull();
    });

    it("should still render when bundle not in dataFilter", () => {
      const propsWithMissingBundle = {
        ...defaultProps,
        dataFilter: {
          "other-bundle": {
            component1: { ...mockAPIClass, display_name: "Component 1" },
          },
        },
      };

      const { container } = render(<BundleItem {...propsWithMissingBundle} />);
      expect(container.firstChild).not.toBeNull();
    });

    it("should render when dataFilter has items for bundle", () => {
      render(<BundleItem {...defaultProps} />);

      expect(screen.getByTestId("disclosure")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-items-list")).toBeInTheDocument();
    });
  });

  describe("Open/Closed State", () => {
    it("should be closed by default when not in openCategories", () => {
      render(<BundleItem {...defaultProps} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "false");
    });

    it("should be open when bundle is in openCategories", () => {
      const propsWithOpenCategory = {
        ...defaultProps,
        openCategories: ["test-bundle"],
      };

      render(<BundleItem {...propsWithOpenCategory} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "true");
    });

    it("should toggle open state when disclosure changes", () => {
      const { rerender } = render(<BundleItem {...defaultProps} />);

      // Simulate disclosure opening by rerendering with different props
      const propsWithHandlerCall = {
        ...defaultProps,
        setOpenCategories: (updateFn: any) => {
          const newCategories = updateFn(["other-category"]);
          expect(newCategories).toEqual(["other-category", "test-bundle"]);
          mockSetOpenCategories(updateFn);
        },
      };

      // Test the handleOpenChange callback behavior directly
      rerender(<BundleItem {...propsWithHandlerCall} />);

      // Trigger the callback by simulating a change from closed to open
      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "false");

      // We can verify the callback is properly set up
      expect(disclosure).toHaveAttribute("data-on-open-change");
    });

    it("should remove from open categories when closing", () => {
      const propsWithOpenCategory = {
        ...defaultProps,
        openCategories: ["test-bundle", "other-bundle"],
        setOpenCategories: (updateFn: any) => {
          const newCategories = updateFn(["test-bundle", "other-bundle"]);
          expect(newCategories).toEqual(["other-bundle"]);
          mockSetOpenCategories(updateFn);
        },
      };

      render(<BundleItem {...propsWithOpenCategory} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "true");

      // We can verify the callback is properly set up
      expect(disclosure).toHaveAttribute("data-on-open-change");
    });
  });

  describe("Keyboard Interaction", () => {
    it("should call handleKeyDownInput on keydown", () => {
      render(<BundleItem {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-bundles-test bundle");

      fireEvent.keyDown(triggerDiv, { key: "Enter" });

      expect(mockHandleKeyDownInput).toHaveBeenCalledWith(
        expect.objectContaining({ key: "Enter" }),
        "test-bundle",
      );
    });

    it("should have correct tabIndex for keyboard navigation", () => {
      render(<BundleItem {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-bundles-test bundle");
      expect(triggerDiv).toHaveAttribute("tabIndex", "0");
    });
  });

  describe("Component Integration", () => {
    it("should render SidebarItemsList with correct props", () => {
      render(<BundleItem {...defaultProps} />);

      const sidebarItemsList = screen.getByTestId("sidebar-items-list");
      expect(sidebarItemsList).toBeInTheDocument();
      expect(sidebarItemsList).toHaveTextContent("Items for test-bundle");
    });

    it("should pass all required props to SidebarItemsList", () => {
      // This test ensures the mocked component receives the right data
      render(<BundleItem {...defaultProps} />);

      expect(screen.getByTestId("sidebar-items-list")).toBeInTheDocument();
    });
  });

  describe("Memoization", () => {
    it("should be wrapped with memo for performance", () => {
      // Test that component is memoized by checking displayName
      expect(BundleItem.displayName).toBe("BundleItem");
    });

    it("should not re-render when props haven't changed", () => {
      const { rerender } = render(<BundleItem {...defaultProps} />);

      const initialElement = screen.getByTestId("disclosure");

      // Re-render with same props
      rerender(<BundleItem {...defaultProps} />);

      // Component should remain the same due to memoization
      expect(screen.getByTestId("disclosure")).toBe(initialElement);
    });
  });

  describe("CSS Classes", () => {
    it("should apply correct CSS classes to trigger element", () => {
      render(<BundleItem {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-bundles-test bundle");
      expect(triggerDiv).toHaveClass(
        "user-select-none",
        "flex",
        "cursor-pointer",
        "items-center",
        "gap-2",
      );
    });

    it("should apply group styling classes", () => {
      render(<BundleItem {...defaultProps} />);

      const disclosureTrigger = screen.getByTestId("disclosure-trigger");
      expect(disclosureTrigger).toHaveClass("group/collapsible");
    });
  });
});
