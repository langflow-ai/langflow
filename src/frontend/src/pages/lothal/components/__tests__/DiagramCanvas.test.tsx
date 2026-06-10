import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import type {
  DiagramEdge,
  DiagramNode,
} from "@/controllers/API/queries/lothal";

// Stub @xyflow/react: jsdom can't lay out the real canvas, and the unit under
// test is DiagramCanvas's wiring — its own provider, the id/zoomOnScroll
// pass-through, and the `chrome` toggle for controls/minimap/legend.
jest.mock("@xyflow/react", () => ({
  ReactFlow: ({
    children,
    id,
    zoomOnScroll,
    nodes,
    edges,
  }: {
    children?: ReactNode;
    id?: string;
    zoomOnScroll?: boolean;
    nodes: unknown[];
    edges: unknown[];
  }) => (
    <div
      data-testid="react-flow"
      data-id={id ?? ""}
      data-zoom-on-scroll={String(zoomOnScroll)}
      data-nodes={nodes.length}
      data-edges={edges.length}
    >
      {children}
    </div>
  ),
  ReactFlowProvider: ({ children }: { children?: ReactNode }) => (
    <div data-testid="rf-provider">{children}</div>
  ),
  Background: () => <div data-testid="rf-background" />,
  BackgroundVariant: { Dots: "dots" },
  Controls: () => <div data-testid="rf-controls" />,
  MiniMap: () => <div data-testid="rf-minimap" />,
  Panel: ({ children }: { children?: ReactNode }) => (
    <div data-testid="rf-panel">{children}</div>
  ),
  // Used by the ActorNode/SystemNode modules pulled in via nodeTypes.
  Handle: () => null,
  Position: { Left: "left", Right: "right" },
}));

import { DiagramCanvas } from "../DiagramCanvas";

const nodes: DiagramNode[] = [
  {
    id: "a",
    type: "actorNode",
    position: { x: 0, y: 0 },
    data: { label: "User" },
  },
  {
    id: "b",
    type: "systemNode",
    position: { x: 100, y: 0 },
    data: { label: "API" },
  },
];
const edges: DiagramEdge[] = [
  { id: "e1", source: "a", target: "b", label: "call", data: { order: 1 } },
];

describe("DiagramCanvas", () => {
  it("wraps the flow in its own provider so multiple canvases on one page don't share a store", () => {
    render(<DiagramCanvas nodes={nodes} edges={edges} />);
    const provider = screen.getByTestId("rf-provider");
    expect(provider).toContainElement(screen.getByTestId("react-flow"));
  });

  it("maps the contract nodes/edges and passes id and zoomOnScroll through", () => {
    render(
      <DiagramCanvas
        nodes={nodes}
        edges={edges}
        id="landing-hero"
        zoomOnScroll={false}
      />,
    );
    const flow = screen.getByTestId("react-flow");
    expect(flow).toHaveAttribute("data-nodes", "2");
    expect(flow).toHaveAttribute("data-edges", "1");
    expect(flow).toHaveAttribute("data-id", "landing-hero");
    expect(flow).toHaveAttribute("data-zoom-on-scroll", "false");
  });

  it("defaults to full chrome with zoom-on-scroll enabled (the Workspace behavior)", () => {
    render(<DiagramCanvas nodes={nodes} edges={edges} />);
    expect(screen.getByTestId("react-flow")).toHaveAttribute(
      "data-zoom-on-scroll",
      "true",
    );
    expect(screen.getByTestId("rf-controls")).toBeInTheDocument();
    expect(screen.getByTestId("rf-minimap")).toBeInTheDocument();
    expect(screen.getByTestId("rf-panel")).toBeInTheDocument(); // legend
    expect(screen.getByTestId("rf-background")).toBeInTheDocument();
  });

  it("chrome={false} hides controls, minimap, and legend but keeps the dotted background", () => {
    render(<DiagramCanvas nodes={nodes} edges={edges} chrome={false} />);
    expect(screen.queryByTestId("rf-controls")).not.toBeInTheDocument();
    expect(screen.queryByTestId("rf-minimap")).not.toBeInTheDocument();
    expect(screen.queryByTestId("rf-panel")).not.toBeInTheDocument();
    expect(screen.getByTestId("rf-background")).toBeInTheDocument();
  });
});
