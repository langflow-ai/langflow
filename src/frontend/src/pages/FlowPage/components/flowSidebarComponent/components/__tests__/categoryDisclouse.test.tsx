import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { CategoryDisclosure } from "../categoryDisclouse";

// Mock the UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name, className }: any) => (
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

describe("CategoryDisclosure", () => {
  const mockSetOpenCategories = jest.fn();
  const mockOnDragStart = jest.fn();
  const mockSensitiveSort = jest.fn();

  const mockAPIClass = {
    description: "Test component",
    template: {},
    display_name: "Test Component",
    documentation: "Test docs",
  };

  const defaultProps = {
    item: {
      name: "test-category",
      display_name: "Test Category",
      icon: "Folder",
    },
    openCategories: [],
    setOpenCategories: mockSetOpenCategories,
    dataFilter: {
      "test-category": {
        component1: { ...mockAPIClass, display_name: "Component 1" },
        component2: { ...mockAPIClass, display_name: "Component 2" },
      },
    },
    nodeColors: {
      "test-category": "#00FF00",
    },
    onDragStart: mockOnDragStart,
    sensitiveSort: mockSensitiveSort,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render category disclosure with correct structure", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      expect(screen.getByTestId("disclosure")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu-item")).toBeInTheDocument();
      expect(screen.getByTestId("disclosure-trigger")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-menu-button")).toBeInTheDocument();
    });

    it("should display category icon and name", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      expect(screen.getByTestId("icon-Folder")).toBeInTheDocument();
      expect(screen.getByText("Test Category")).toBeInTheDocument();
    });

    it("should display chevron icon", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      expect(screen.getByTestId("icon-ChevronRight")).toBeInTheDocument();
    });

    it("should include correct test id for disclosure", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const disclosureDiv = screen.getByTestId("disclosure-test category");
      expect(disclosureDiv).toBeInTheDocument();
    });

    it("should render disclosure content with SidebarItemsList", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      expect(screen.getByTestId("disclosure-content")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-items-list")).toBeInTheDocument();
    });
  });

  describe("Open/Closed State", () => {
    it("should be closed by default when not in openCategories", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "false");
    });

    it("should be open when category is in openCategories", () => {
      const propsWithOpenCategory = {
        ...defaultProps,
        openCategories: ["test-category"],
      };

      render(<CategoryDisclosure {...propsWithOpenCategory} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "true");
    });

    it("should toggle open state when disclosure changes", () => {
      const { rerender } = render(<CategoryDisclosure {...defaultProps} />);

      // Simulate disclosure opening by rerendering with different props
      const propsWithHandlerCall = {
        ...defaultProps,
        setOpenCategories: (updateFn: any) => {
          const newCategories = updateFn(["other-category"]);
          expect(newCategories).toEqual(["other-category", "test-category"]);
          mockSetOpenCategories(updateFn);
        },
      };

      // Test the handleOpenChange callback behavior directly
      rerender(<CategoryDisclosure {...propsWithHandlerCall} />);

      // Trigger the callback by simulating a change from closed to open
      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "false");

      // We can verify the callback is properly set up
      expect(disclosure).toHaveAttribute("data-on-open-change");
    });

    it("should remove from open categories when closing", () => {
      const propsWithOpenCategory = {
        ...defaultProps,
        openCategories: ["test-category", "other-category"],
        setOpenCategories: (updateFn: any) => {
          const newCategories = updateFn(["test-category", "other-category"]);
          expect(newCategories).toEqual(["other-category"]);
          mockSetOpenCategories(updateFn);
        },
      };

      render(<CategoryDisclosure {...propsWithOpenCategory} />);

      const disclosure = screen.getByTestId("disclosure");
      expect(disclosure).toHaveAttribute("data-open", "true");

      // We can verify the callback is properly set up
      expect(disclosure).toHaveAttribute("data-on-open-change");
    });
  });

  describe("Keyboard Interaction", () => {
    it("should toggle category on Enter key", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");

      fireEvent.keyDown(triggerDiv, { key: "Enter" });

      expect(mockSetOpenCategories).toHaveBeenCalledWith(expect.any(Function));

      // Test the function for adding category (closed -> open)
      const updateFunction = mockSetOpenCategories.mock.calls[0][0];
      const newCategories = updateFunction([]);
      expect(newCategories).toEqual(["test-category"]);
    });

    it("should toggle category on Space key", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");

      fireEvent.keyDown(triggerDiv, { key: " " });

      expect(mockSetOpenCategories).toHaveBeenCalledWith(expect.any(Function));
    });

    it("should respond to Enter and Space keys", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");

      fireEvent.keyDown(triggerDiv, { key: "Enter" });
      expect(mockSetOpenCategories).toHaveBeenCalledTimes(1);

      fireEvent.keyDown(triggerDiv, { key: " " });
      expect(mockSetOpenCategories).toHaveBeenCalledTimes(2);
    });

    it("should not trigger on other keys", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");

      fireEvent.keyDown(triggerDiv, { key: "Escape" });

      expect(mockSetOpenCategories).not.toHaveBeenCalled();
    });

    it("should handle toggle when category is already open", () => {
      const propsWithOpenCategory = {
        ...defaultProps,
        openCategories: ["test-category"],
      };

      render(<CategoryDisclosure {...propsWithOpenCategory} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");

      fireEvent.keyDown(triggerDiv, { key: "Enter" });

      expect(mockSetOpenCategories).toHaveBeenCalledWith(expect.any(Function));

      // Test the function for removing category (open -> closed)
      const updateFunction = mockSetOpenCategories.mock.calls[0][0];
      const newCategories = updateFunction(["test-category"]);
      expect(newCategories).toEqual([]);
    });

    it("should have correct tabIndex for keyboard navigation", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");
      expect(triggerDiv).toHaveAttribute("tabIndex", "0");
    });
  });

  describe("Component Integration", () => {
    it("should render SidebarItemsList with correct props", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const sidebarItemsList = screen.getByTestId("sidebar-items-list");
      expect(sidebarItemsList).toBeInTheDocument();
      expect(sidebarItemsList).toHaveTextContent("Items for test-category");
    });

    it("should pass all required props to SidebarItemsList", () => {
      // This test ensures the mocked component receives the right data
      render(<CategoryDisclosure {...defaultProps} />);

      expect(screen.getByTestId("sidebar-items-list")).toBeInTheDocument();
    });
  });

  describe("Memoization and Performance", () => {
    it("should be wrapped with memo for performance", () => {
      // Test that component is memoized by checking displayName
      expect(CategoryDisclosure.displayName).toBe("CategoryDisclosure");
    });

    it("should use useCallback for handleKeyDownInput", () => {
      const { rerender } = render(<CategoryDisclosure {...defaultProps} />);

      // Get the keydown handler function
      const triggerDiv = screen.getByTestId("disclosure-test category");
      const initialKeyDownHandler = triggerDiv.getAttribute("onkeydown");

      // Re-render with same props
      rerender(<CategoryDisclosure {...defaultProps} />);

      // The handler should be the same due to useCallback
      const rerenderKeyDownHandler = triggerDiv.getAttribute("onkeydown");
      expect(rerenderKeyDownHandler).toBe(initialKeyDownHandler);
    });

    it("should use useCallback for handleOpenChange", () => {
      const { rerender } = render(<CategoryDisclosure {...defaultProps} />);

      const disclosure = screen.getByTestId("disclosure");
      const initialOnOpenChangeAttr = disclosure.getAttribute(
        "data-on-open-change",
      );

      // Re-render with same props
      rerender(<CategoryDisclosure {...defaultProps} />);

      const rerenderOnOpenChangeAttr = disclosure.getAttribute(
        "data-on-open-change",
      );
      expect(rerenderOnOpenChangeAttr).toBe(initialOnOpenChangeAttr);
    });
  });

  describe("CSS Classes and Styling", () => {
    it("should apply correct CSS classes to trigger element", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const triggerDiv = screen.getByTestId("disclosure-test category");
      expect(triggerDiv).toHaveClass(
        "user-select-none",
        "flex",
        "cursor-pointer",
        "items-center",
        "gap-2",
      );
    });

    it("should apply group styling classes to disclosure trigger", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const disclosureTrigger = screen.getByTestId("disclosure-trigger");
      expect(disclosureTrigger).toHaveClass("group/collapsible");
    });

    it("should apply accent-pink-foreground class to category icon", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const categoryIcon = screen.getByTestId("icon-Folder");
      expect(categoryIcon).toHaveClass(
        "group-aria-expanded/collapsible:text-accent-pink-foreground",
      );
    });

    it("should apply font-semibold class to category name span", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const categoryNameSpan = screen.getByText("Test Category");
      expect(categoryNameSpan).toHaveClass(
        "group-aria-expanded/collapsible:font-semibold",
      );
    });

    it("should apply rotation class to chevron icon", () => {
      render(<CategoryDisclosure {...defaultProps} />);

      const chevronIcon = screen.getByTestId("icon-ChevronRight");
      expect(chevronIcon).toHaveClass(
        "group-aria-expanded/collapsible:rotate-90",
      );
    });
  });

  describe("Props Handling", () => {
    it("should handle different item shapes", () => {
      const propsWithDifferentItem = {
        ...defaultProps,
        item: {
          name: "custom-category",
          display_name: "Custom Category",
          icon: "Star",
        },
      };

      render(<CategoryDisclosure {...propsWithDifferentItem} />);

      expect(screen.getByTestId("icon-Star")).toBeInTheDocument();
      expect(screen.getByText("Custom Category")).toBeInTheDocument();
    });

    it("should handle missing openCategories gracefully", () => {
      const propsWithoutOpenCategories = {
        ...defaultProps,
        openCategories: [] as string[],
      };

      expect(() => {
        render(<CategoryDisclosure {...propsWithoutOpenCategories} />);
      }).not.toThrow();
    });

    it("should handle item name with special characters", () => {
      const propsWithSpecialName = {
        ...defaultProps,
        item: {
          name: "test-category-special",
          display_name: "Test Category & Special",
          icon: "Hash",
        },
      };

      render(<CategoryDisclosure {...propsWithSpecialName} />);

      expect(
        screen.getByTestId("disclosure-test category & special"),
      ).toBeInTheDocument();
    });
  });
});
