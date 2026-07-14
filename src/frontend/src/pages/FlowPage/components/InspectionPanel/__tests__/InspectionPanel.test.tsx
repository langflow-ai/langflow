import { render, screen } from "@testing-library/react";
import type { AllNodeType } from "@/types/flow";
import InspectionPanel from "../index";

jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...props }: any) => (
    <div data-testid="xyflow-panel" {...props}>
      {children}
    </div>
  ),
}));

jest.mock("../components/InspectionPanelHeader", () => {
  return function MockInspectionPanelHeader() {
    return <div data-testid="inspection-panel-header">Component Parameters</div>;
  };
});

jest.mock("../components/InspectionPanelFields", () => {
  return function MockInspectionPanelFields({ data }: any) {
    return (
      <div data-testid="inspection-panel-fields">
        Fields for {data?.id || "unknown"}
      </div>
    );
  };
});

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <hr data-testid="separator" />,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("InspectionPanel", () => {
  const createMockNode = (overrides: Partial<AllNodeType> = {}): AllNodeType =>
    ({
      id: "test-node-123",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "test-node-123",
        type: "TestComponent",
        node: { template: {}, display_name: "Test" },
      },
      ...overrides,
    }) as AllNodeType;

  it("renders header and fields for a selected generic node", () => {
    render(<InspectionPanel selectedNode={createMockNode()} />);

    expect(screen.getByTestId("inspection-panel-header")).toBeInTheDocument();
    expect(screen.getByTestId("inspection-panel-fields")).toBeInTheDocument();
    expect(screen.getByText(/Fields for test-node-123/)).toBeInTheDocument();
  });

  it("renders nothing when no node is selected", () => {
    render(<InspectionPanel selectedNode={null} />);

    expect(
      screen.queryByTestId("inspection-panel-header"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing for non-generic nodes", () => {
    render(
      <InspectionPanel
        selectedNode={createMockNode({ type: "noteNode" } as any)}
      />,
    );

    expect(
      screen.queryByTestId("inspection-panel-header"),
    ).not.toBeInTheDocument();
  });

  it("remounts fields when the selected node changes", () => {
    const { rerender } = render(
      <InspectionPanel selectedNode={createMockNode()} />,
    );
    expect(screen.getByText(/Fields for test-node-123/)).toBeInTheDocument();

    const otherNode = createMockNode();
    otherNode.id = "other-node-456";
    otherNode.data = { ...otherNode.data, id: "other-node-456" } as any;
    rerender(<InspectionPanel selectedNode={otherNode} />);

    expect(screen.getByText(/Fields for other-node-456/)).toBeInTheDocument();
  });
});
