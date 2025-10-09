import { render, screen } from "@testing-library/react";
import SidebarItemsList from "../sidebarItemsList";

// Mock external dependencies
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content, side }: any) => (
    <div data-testid="tooltip" data-content={content} data-side={side}>
      {children}
    </div>
  ),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      nodes: [
        { id: "node1", type: "ChatInput" },
        { id: "node2", type: "Text" },
      ],
    }),
  ),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  checkChatInput: jest.fn((nodes) =>
    nodes.some((node: any) => node.type === "ChatInput"),
  ),
  checkWebhookInput: jest.fn((nodes) =>
    nodes.some((node: any) => node.type === "Webhook"),
  ),
}));

jest.mock("@/utils/utils", () => ({
  removeCountFromString: jest.fn((str) => str.replace(/\d+$/, "")),
}));

jest.mock("../../helpers/disable-item", () => ({
  disableItem: jest.fn((itemName, uniqueInputs) => {
    if (itemName === "ChatInput" && uniqueInputs.chatInput) return true;
    if (itemName === "Webhook" && uniqueInputs.webhookInput) return true;
    return false;
  }),
}));

jest.mock("../../helpers/get-disabled-tooltip", () => ({
  getDisabledTooltip: jest.fn((itemName, uniqueInputs) => {
    if (itemName === "ChatInput" && uniqueInputs.chatInput)
      return "Chat Input already added";
    if (itemName === "Webhook" && uniqueInputs.webhookInput)
      return "Webhook already added";
    return "";
  }),
}));

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
      data-testid={`draggable-${itemName}`}
      data-section-name={sectionName}
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
      onClick={() =>
        onDragStart?.({ type: "dragstart" }, { type: itemName, node: apiClass })
      }
    >
      {display_name}
    </div>
  ),
}));

describe("SidebarItemsList", () => {
  const mockOnDragStart = jest.fn();
  const mockSensitiveSort = jest.fn((a, b) => a.localeCompare(b));

  const defaultItem = {
    name: "TestCategory",
    icon: "TestIcon",
  };

  const defaultDataFilter = {
    TestCategory: {
      Component1: {
        display_name: "Component 1",
        icon: "Component1Icon",
        error: false,
        official: true,
        beta: false,
        legacy: false,
        priority: 1,
        score: 10,
      },
      Component2: {
        display_name: "Component 2",
        icon: "Component2Icon",
        error: false,
        official: false,
        beta: true,
        legacy: false,
        priority: 2,
        score: 20,
      },
      ChatInput: {
        display_name: "Chat Input",
        icon: "ChatIcon",
        error: false,
        official: true,
        beta: false,
        legacy: false,
        priority: 0,
        score: 5,
      },
      Webhook: {
        display_name: "Webhook",
        icon: "WebhookIcon",
        error: true,
        official: true,
        beta: false,
        legacy: true,
        priority: 3,
        score: 30,
      },
    },
  };

  const defaultNodeColors = {
    TestCategory: "#FF0000",
  };

  const defaultProps = {
    item: defaultItem,
    dataFilter: defaultDataFilter,
    nodeColors: defaultNodeColors,
    onDragStart: mockOnDragStart,
    sensitiveSort: mockSensitiveSort,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render items list container", () => {
      const { container } = render(<SidebarItemsList {...defaultProps} />);

      const mainContainer = container.firstChild as HTMLElement;
      expect(mainContainer).toHaveClass("flex", "flex-col", "gap-1", "py-1");
    });

    it("should render all components from dataFilter", () => {
      render(<SidebarItemsList {...defaultProps} />);

      expect(screen.getByTestId("draggable-Component1")).toBeInTheDocument();
      expect(screen.getByTestId("draggable-Component2")).toBeInTheDocument();
      expect(screen.getByTestId("draggable-ChatInput")).toBeInTheDocument();
      expect(screen.getByTestId("draggable-Webhook")).toBeInTheDocument();
    });

    it("should wrap components in tooltips", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const tooltips = screen.getAllByTestId("tooltip");
      expect(tooltips).toHaveLength(4); // One for each component
    });

    it("should display component names in tooltips", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const tooltips = screen.getAllByTestId("tooltip");
      expect(tooltips[0]).toHaveAttribute("data-content", "Chat Input");
      expect(tooltips[1]).toHaveAttribute("data-content", "Component 1");
      expect(tooltips[2]).toHaveAttribute("data-content", "Component 2");
      expect(tooltips[3]).toHaveAttribute("data-content", "Webhook");
    });

    it("should set tooltip side to right", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const tooltips = screen.getAllByTestId("tooltip");
      tooltips.forEach((tooltip) => {
        expect(tooltip).toHaveAttribute("data-side", "right");
      });
    });
  });

  describe("Component Sorting", () => {
    it("should sort components by priority when available", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const draggables = screen.getAllByTestId(/^draggable-/);
      expect(draggables[0]).toHaveAttribute("data-item-name", "ChatInput"); // priority 0
      expect(draggables[1]).toHaveAttribute("data-item-name", "Component1"); // priority 1
      expect(draggables[2]).toHaveAttribute("data-item-name", "Component2"); // priority 2
      expect(draggables[3]).toHaveAttribute("data-item-name", "Webhook"); // priority 3
    });

    it("should fall back to score sorting when priorities are equal", () => {
      const dataWithEqualPriorities = {
        TestCategory: {
          Component1: {
            ...defaultDataFilter.TestCategory.Component1,
            priority: 1,
            score: 20,
          },
          Component2: {
            ...defaultDataFilter.TestCategory.Component2,
            priority: 1,
            score: 10,
          },
        },
      };

      const propsWithEqualPriorities = {
        ...defaultProps,
        dataFilter: dataWithEqualPriorities,
      };

      render(<SidebarItemsList {...propsWithEqualPriorities} />);

      const draggables = screen.getAllByTestId(/^draggable-/);
      expect(draggables[0]).toHaveAttribute("data-item-name", "Component2"); // score 10
      expect(draggables[1]).toHaveAttribute("data-item-name", "Component1"); // score 20
    });

    it("should use sensitive sort when no score available", () => {
      const dataWithoutScores = {
        TestCategory: {
          ZComponent: {
            ...defaultDataFilter.TestCategory.Component1,
            priority: 1,
            score: undefined,
            display_name: "Z Component",
          },
          AComponent: {
            ...defaultDataFilter.TestCategory.Component2,
            priority: 1,
            score: undefined,
            display_name: "A Component",
          },
        },
      };

      const propsWithoutScores = {
        ...defaultProps,
        dataFilter: dataWithoutScores,
      };

      render(<SidebarItemsList {...propsWithoutScores} />);

      expect(mockSensitiveSort).toHaveBeenCalledWith(
        "A Component",
        "Z Component",
      );
    });

    it("should handle missing priority as maximum value", () => {
      const dataWithMissingPriorities = {
        TestCategory: {
          Component1: {
            ...defaultDataFilter.TestCategory.Component1,
            priority: 1,
          },
          Component2: {
            ...defaultDataFilter.TestCategory.Component2,
            priority: undefined,
          },
        },
      };

      const propsWithMissingPriorities = {
        ...defaultProps,
        dataFilter: dataWithMissingPriorities,
      };

      render(<SidebarItemsList {...propsWithMissingPriorities} />);

      const draggables = screen.getAllByTestId(/^draggable-/);
      expect(draggables[0]).toHaveAttribute("data-item-name", "Component1"); // priority 1
      expect(draggables[1]).toHaveAttribute("data-item-name", "Component2"); // priority undefined (max)
    });
  });

  describe("Draggable Component Props", () => {
    it("should pass correct props to regular components", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const component1 = screen.getByTestId("draggable-Component1");
      expect(component1).toHaveAttribute("data-section-name", "TestCategory");
      expect(component1).toHaveAttribute("data-icon", "Component1Icon");
      expect(component1).toHaveAttribute("data-color", "#FF0000");
      expect(component1).toHaveAttribute("data-display-name", "Component 1");
      expect(component1).toHaveAttribute("data-official", "true");
      expect(component1).toHaveAttribute("data-beta", "false");
      expect(component1).toHaveAttribute("data-legacy", "false");
      expect(component1).toHaveAttribute("data-disabled", "false");
      expect(component1).toHaveAttribute("data-disabled-tooltip", "");
    });

    it("should handle component with error", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const webhook = screen.getByTestId("draggable-Webhook");
      expect(webhook).toHaveAttribute("data-error", "true");
    });

    it("should handle component with beta flag", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const component2 = screen.getByTestId("draggable-Component2");
      expect(component2).toHaveAttribute("data-beta", "true");
      expect(component2).toHaveAttribute("data-official", "false");
    });

    it("should handle component with legacy flag", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const webhook = screen.getByTestId("draggable-Webhook");
      expect(webhook).toHaveAttribute("data-legacy", "true");
    });

    it("should use fallback icon when component icon missing", () => {
      const dataWithMissingIcon = {
        TestCategory: {
          Component1: {
            ...defaultDataFilter.TestCategory.Component1,
            icon: undefined,
          },
        },
      };

      const propsWithMissingIcon = {
        ...defaultProps,
        dataFilter: dataWithMissingIcon,
      };

      render(<SidebarItemsList {...propsWithMissingIcon} />);

      const component1 = screen.getByTestId("draggable-Component1");
      expect(component1).toHaveAttribute("data-icon", "TestIcon"); // Falls back to item.icon
    });

    it("should use Unknown icon when all icons missing", () => {
      const dataWithNoIcon = {
        TestCategory: {
          Component1: {
            ...defaultDataFilter.TestCategory.Component1,
            icon: undefined,
          },
        },
      };

      const propsWithNoIcon = {
        ...defaultProps,
        item: { ...defaultItem, icon: undefined },
        dataFilter: dataWithNoIcon,
      };

      render(<SidebarItemsList {...propsWithNoIcon} />);

      const component1 = screen.getByTestId("draggable-Component1");
      expect(component1).toHaveAttribute("data-icon", "Unknown");
    });
  });

  describe("Special Components (ChatInput/Webhook)", () => {
    it("should handle ChatInput with special logic", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const chatInput = screen.getByTestId("draggable-ChatInput");
      expect(chatInput).toHaveAttribute("data-disabled", "true"); // Should be disabled if already added
      expect(chatInput).toHaveAttribute(
        "data-disabled-tooltip",
        "Chat Input already added",
      );
    });

    it("should handle Webhook with special logic", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const webhook = screen.getByTestId("draggable-Webhook");
      expect(webhook).toHaveAttribute("data-disabled", "false"); // Webhook not added in mock
      expect(webhook).toHaveAttribute("data-disabled-tooltip", "");
    });
  });

  describe("Drag and Drop", () => {
    it("should handle drag start for regular components", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const component1 = screen.getByTestId("draggable-Component1");
      component1.click(); // Simulate drag start

      expect(mockOnDragStart).toHaveBeenCalledWith(
        expect.objectContaining({ type: "dragstart" }),
        expect.objectContaining({
          type: "Component",
          node: defaultDataFilter.TestCategory.Component1,
        }),
      );
    });

    it("should handle drag start for ChatInput", () => {
      render(<SidebarItemsList {...defaultProps} />);

      const chatInput = screen.getByTestId("draggable-ChatInput");
      chatInput.click(); // Simulate drag start

      expect(mockOnDragStart).toHaveBeenCalledWith(
        expect.objectContaining({ type: "dragstart" }),
        expect.objectContaining({
          type: "ChatInput",
          node: defaultDataFilter.TestCategory.ChatInput,
        }),
      );
    });

    it("should remove count from string in drag start", () => {
      const dataWithCount = {
        TestCategory: {
          Component1_2: {
            ...defaultDataFilter.TestCategory.Component1,
            display_name: "Component 1 Copy",
          },
        },
      };

      const propsWithCount = {
        ...defaultProps,
        dataFilter: dataWithCount,
      };

      render(<SidebarItemsList {...propsWithCount} />);

      const component = screen.getByTestId("draggable-Component1_2");
      component.click();

      // removeCountFromString should be called to clean the name
      expect(
        require("@/utils/utils").removeCountFromString,
      ).toHaveBeenCalledWith("Component1_2");
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty dataFilter", () => {
      const propsWithEmptyData = {
        ...defaultProps,
        dataFilter: { TestCategory: {} },
      };

      render(<SidebarItemsList {...propsWithEmptyData} />);

      expect(screen.queryByTestId(/^draggable-/)).not.toBeInTheDocument();
    });

    it("should handle missing node colors", () => {
      const propsWithoutColors = {
        ...defaultProps,
        nodeColors: {},
      };

      render(<SidebarItemsList {...propsWithoutColors} />);

      const component1 = screen.getByTestId("draggable-Component1");
      expect(component1).not.toHaveAttribute("data-color"); // undefined color is not set as attribute
    });

    it("should handle components with undefined official property", () => {
      const dataWithUndefinedOfficial = {
        TestCategory: {
          Component1: {
            ...defaultDataFilter.TestCategory.Component1,
            official: undefined,
          },
        },
      };

      const propsWithUndefinedOfficial = {
        ...defaultProps,
        dataFilter: dataWithUndefinedOfficial,
      };

      render(<SidebarItemsList {...propsWithUndefinedOfficial} />);

      const component1 = screen.getByTestId("draggable-Component1");
      expect(component1).toHaveAttribute("data-official", "true"); // Defaults to true
    });

    it("should handle components with missing beta/legacy flags", () => {
      const dataWithMissingFlags = {
        TestCategory: {
          Component1: {
            ...defaultDataFilter.TestCategory.Component1,
            beta: undefined,
            legacy: undefined,
          },
        },
      };

      const propsWithMissingFlags = {
        ...defaultProps,
        dataFilter: dataWithMissingFlags,
      };

      render(<SidebarItemsList {...propsWithMissingFlags} />);

      const component1 = screen.getByTestId("draggable-Component1");
      expect(component1).toHaveAttribute("data-beta", "false"); // Defaults to false
      expect(component1).toHaveAttribute("data-legacy", "false"); // Defaults to false
    });
  });

  describe("Component Structure", () => {
    it("should have correct container structure", () => {
      const { container } = render(<SidebarItemsList {...defaultProps} />);

      const mainContainer = container.firstChild as HTMLElement;
      expect(mainContainer).toHaveClass("flex", "flex-col", "gap-1", "py-1");
    });

    it("should contain all expected child elements", () => {
      render(<SidebarItemsList {...defaultProps} />);

      expect(screen.getAllByTestId("tooltip")).toHaveLength(4);
      expect(screen.getAllByTestId(/^draggable-/)).toHaveLength(4);
    });
  });

  describe("Props Handling", () => {
    it("should handle different item names", () => {
      const propsWithDifferentItem = {
        ...defaultProps,
        item: { name: "CustomCategory", icon: "CustomIcon" },
        dataFilter: {
          CustomCategory: {
            CustomComponent: {
              display_name: "Custom Component",
              icon: "CustomComponentIcon",
              error: false,
              official: true,
              beta: false,
              legacy: false,
              priority: 1,
            },
          },
        },
        nodeColors: { CustomCategory: "#00FF00" },
      };

      render(<SidebarItemsList {...propsWithDifferentItem} />);

      const customComponent = screen.getByTestId("draggable-CustomComponent");
      expect(customComponent).toHaveAttribute(
        "data-section-name",
        "CustomCategory",
      );
      expect(customComponent).toHaveAttribute("data-color", "#00FF00");
    });

    it("should handle different callback functions", () => {
      const alternativeOnDragStart = jest.fn();
      const alternativeSensitiveSort = jest.fn((a, b) => b.localeCompare(a)); // Reverse sort

      const propsWithDifferentCallbacks = {
        ...defaultProps,
        onDragStart: alternativeOnDragStart,
        sensitiveSort: alternativeSensitiveSort,
      };

      render(<SidebarItemsList {...propsWithDifferentCallbacks} />);

      const component1 = screen.getByTestId("draggable-Component1");
      component1.click();

      expect(alternativeOnDragStart).toHaveBeenCalled();
      expect(mockOnDragStart).not.toHaveBeenCalled();
    });
  });

  describe("Integration", () => {
    it("should integrate with all mocked dependencies correctly", () => {
      render(<SidebarItemsList {...defaultProps} />);

      // Verify all mocked functions were called
      expect(require("@/stores/flowStore").default).toHaveBeenCalled();
      expect(
        require("@/utils/reactflowUtils").checkChatInput,
      ).toHaveBeenCalled();
      expect(
        require("@/utils/reactflowUtils").checkWebhookInput,
      ).toHaveBeenCalled();
      expect(
        require("../../helpers/disable-item").disableItem,
      ).toHaveBeenCalled();
      expect(
        require("../../helpers/get-disabled-tooltip").getDisabledTooltip,
      ).toHaveBeenCalled();
    });
  });
});
