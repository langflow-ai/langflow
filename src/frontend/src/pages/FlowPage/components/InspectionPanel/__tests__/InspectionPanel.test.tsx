import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InspectionPanel from "../index";
import type { AllNodeType } from "@/types/flow";

// Mock framer-motion
jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock @xyflow/react Panel
jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...props }: any) => (
    <div data-testid="xyflow-panel" {...props}>
      {children}
    </div>
  ),
}));

// Mock InspectionPanelHeader
jest.mock("../components/InspectionPanelHeader", () => {
  return function MockInspectionPanelHeader({
    data,
    onClose,
    isEditingFields,
    setIsEditingFields,
  }: any) {
    return (
      <div data-testid="inspection-panel-header">
        <span>Header for {data?.id || "unknown"}</span>
        {onClose && (
          <button onClick={onClose} data-testid="mock-close-button">
            Close
          </button>
        )}
        <button
          onClick={() => setIsEditingFields(!isEditingFields)}
          data-testid="edit-fields-button"
          className={isEditingFields ? "text-primary" : "text-muted-foreground"}
        >
          {isEditingFields ? "Done" : "Edit"}
        </button>
      </div>
    );
  };
});

// Mock InspectionPanelFields
jest.mock("../components/InspectionPanelFields", () => {
  return function MockInspectionPanelFields({ data, isEditingFields }: any) {
    return (
      <div data-testid="inspection-panel-fields">
        <span>Fields for {data?.id || "unknown"}</span>
        <span data-testid="edit-mode-indicator">
          {isEditingFields ? "Editing" : "Viewing"}
        </span>
      </div>
    );
  };
});

// Mock Separator
jest.mock("@/components/ui/separator", () => ({
  Separator: () => <hr data-testid="separator" />,
}));

// Mock Button
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

// Mock utils
jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("InspectionPanel", () => {
  const createMockNode = (overrides = {}): AllNodeType => ({
    id: "test-node-123",
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id: "test-node-123",
      type: "TestComponent",
      node: {
        display_name: "Test Node",
        description: "Test description",
        documentation: "",
        template: {},
      },
      ...overrides,
    },
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should not render when selectedNode is null", () => {
      render(<InspectionPanel selectedNode={null} />);

      expect(screen.queryByTestId("xyflow-panel")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("inspection-panel-header"),
      ).not.toBeInTheDocument();
    });

    it("should render panel when genericNode is selected", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      expect(screen.getByTestId("xyflow-panel")).toBeInTheDocument();
      expect(screen.getByTestId("inspection-panel-header")).toBeInTheDocument();
      expect(screen.getByTestId("inspection-panel-fields")).toBeInTheDocument();
    });

    it("should not render for non-genericNode types", () => {
      const mockNode = createMockNode();
      mockNode.type = "customNode";

      render(<InspectionPanel selectedNode={mockNode} />);

      expect(screen.queryByTestId("xyflow-panel")).not.toBeInTheDocument();
    });

    it("should render edit fields button", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const editButton = screen.getByTestId("edit-fields-button");
      expect(editButton).toBeInTheDocument();
      expect(editButton).toHaveTextContent("Edit");
    });

    it("should render separator", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      expect(screen.getByTestId("separator")).toBeInTheDocument();
    });
  });

  describe("Edit Mode Toggle", () => {
    it("should toggle edit mode when button is clicked", async () => {
      const user = userEvent.setup();
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const editButton = screen.getByTestId("edit-fields-button");
      expect(editButton).toHaveTextContent("Edit");
      expect(screen.getByTestId("edit-mode-indicator")).toHaveTextContent(
        "Viewing",
      );

      await user.click(editButton);

      expect(editButton).toHaveTextContent("Done");
      expect(screen.getByTestId("edit-mode-indicator")).toHaveTextContent(
        "Editing",
      );
    });

    it("should toggle back to view mode", async () => {
      const user = userEvent.setup();
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const editButton = screen.getByTestId("edit-fields-button");

      // Enter edit mode
      await user.click(editButton);
      expect(editButton).toHaveTextContent("Done");

      // Exit edit mode
      await user.click(editButton);
      expect(editButton).toHaveTextContent("Edit");
      expect(screen.getByTestId("edit-mode-indicator")).toHaveTextContent(
        "Viewing",
      );
    });

    it("should apply correct styling in edit mode", async () => {
      const user = userEvent.setup();
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const editButton = screen.getByTestId("edit-fields-button");

      await user.click(editButton);

      expect(editButton).toHaveClass("text-primary");
    });

    it("should apply correct styling in view mode", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const editButton = screen.getByTestId("edit-fields-button");

      expect(editButton).toHaveClass("text-muted-foreground");
    });
  });

  describe("Node Change Handling", () => {
    it("should reset edit mode when node changes", async () => {
      const user = userEvent.setup();
      const mockNode1 = createMockNode();
      const { rerender } = render(<InspectionPanel selectedNode={mockNode1} />);

      const editButton = screen.getByTestId("edit-fields-button");

      // Enter edit mode
      await user.click(editButton);
      expect(editButton).toHaveTextContent("Done");

      // Change node
      const mockNode2 = createMockNode({ id: "different-node-456" });
      mockNode2.id = "different-node-456";
      mockNode2.data.id = "different-node-456";

      rerender(<InspectionPanel selectedNode={mockNode2} />);

      // Edit mode should be reset
      await waitFor(() => {
        expect(screen.getByTestId("edit-fields-button")).toHaveTextContent(
          "Edit",
        );
      });
    });

    it("should maintain edit mode when same node is re-rendered", async () => {
      const user = userEvent.setup();
      const mockNode = createMockNode();
      const { rerender } = render(<InspectionPanel selectedNode={mockNode} />);

      const editButton = screen.getByTestId("edit-fields-button");

      // Enter edit mode
      await user.click(editButton);
      expect(editButton).toHaveTextContent("Done");

      // Re-render with same node
      rerender(<InspectionPanel selectedNode={mockNode} />);

      // Edit mode should be maintained
      expect(screen.getByTestId("edit-fields-button")).toHaveTextContent(
        "Done",
      );
    });
  });

  describe("Panel Positioning", () => {
    it("should apply correct positioning classes", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const panel = screen.getByTestId("xyflow-panel");
      expect(panel).toHaveClass("!top-[3rem]");
      expect(panel).toHaveClass("!-right-2");
      expect(panel).toHaveClass("!bottom-10");
    });

    it("should apply correct width", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      const panel = screen.getByTestId("xyflow-panel");
      expect(panel).toHaveClass("w-[340px]");
    });
  });

  describe("Component Integration", () => {
    it("should pass correct data to InspectionPanelHeader", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      expect(screen.getByText("Header for test-node-123")).toBeInTheDocument();
    });

    it("should pass correct data to InspectionPanelFields", () => {
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      expect(screen.getByText("Fields for test-node-123")).toBeInTheDocument();
    });

    it("should pass isEditingFields prop correctly", async () => {
      const user = userEvent.setup();
      const mockNode = createMockNode();
      render(<InspectionPanel selectedNode={mockNode} />);

      expect(screen.getByTestId("edit-mode-indicator")).toHaveTextContent(
        "Viewing",
      );

      await user.click(screen.getByTestId("edit-fields-button"));

      expect(screen.getByTestId("edit-mode-indicator")).toHaveTextContent(
        "Editing",
      );
    });

    it("should use node id as key for InspectionPanelFields", () => {
      const mockNode = createMockNode();
      const { container } = render(<InspectionPanel selectedNode={mockNode} />);

      // The key is used internally by React, we can verify the component renders
      expect(screen.getByTestId("inspection-panel-fields")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle node without data gracefully", () => {
      const mockNode = {
        id: "test-node",
        type: "genericNode",
        position: { x: 0, y: 0 },
        data: null as any,
      };

      expect(() => {
        render(<InspectionPanel selectedNode={mockNode} />);
      }).not.toThrow();
    });

    it("should handle rapid node changes", async () => {
      const mockNode1 = createMockNode();
      const { rerender } = render(<InspectionPanel selectedNode={mockNode1} />);

      const mockNode2 = createMockNode({ id: "node-2" });
      mockNode2.id = "node-2";
      mockNode2.data.id = "node-2";

      const mockNode3 = createMockNode({ id: "node-3" });
      mockNode3.id = "node-3";
      mockNode3.data.id = "node-3";

      rerender(<InspectionPanel selectedNode={mockNode2} />);
      rerender(<InspectionPanel selectedNode={mockNode3} />);
      rerender(<InspectionPanel selectedNode={null} />);

      expect(
        screen.queryByTestId("inspection-panel-header"),
      ).not.toBeInTheDocument();
    });
  });
});
