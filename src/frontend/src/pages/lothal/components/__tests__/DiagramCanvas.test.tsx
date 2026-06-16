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

import { ActorNode } from "../ActorNode";
import { DiagramCanvas } from "../DiagramCanvas";
import type { CanvasNodeData } from "../nodeStyles";
import { SystemNode } from "../SystemNode";

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
  { id: "e1", source: "a", target: "b", data: { order: 1, label: "call" } },
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

// Helper that builds the minimal props object ActorNode/SystemNode consume.
// TypeScript's NodeProps<T> carries many required layout fields that only
// xyflow's renderer supplies at runtime; these nodes read only `data`, so the
// helper is typed `any` to spread just `data` into the node under test.
// biome-ignore lint/suspicious/noExplicitAny: test-only minimal node props
function nodeProps(data: CanvasNodeData): any {
  return { data };
}

describe("ActorNode — direct render", () => {
  it("renders the label and falls back to 'Actor' when label is absent", () => {
    render(<ActorNode {...nodeProps({ label: "Alice" })} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("uses 'Actor' as the label fallback when data.label is undefined", () => {
    render(<ActorNode {...nodeProps({})} />);
    expect(screen.getByText("Actor")).toBeInTheDocument();
  });

  it("renders the optional note when supplied", () => {
    render(
      <ActorNode {...nodeProps({ label: "Bob", note: "initiates flow" })} />,
    );
    expect(screen.getByText("initiates flow")).toBeInTheDocument();
  });

  it("omits the note element when data.note is absent", () => {
    const { container } = render(
      <ActorNode {...nodeProps({ label: "Bob" })} />,
    );
    // The note span has small muted text; confirm it's not rendered.
    expect(container.querySelector('[style*="ink-soft"]')).toBeNull();
  });

  it("renders the kind hint when data.kind is supplied", () => {
    render(<ActorNode {...nodeProps({ label: "Alice", kind: "person" })} />);
    expect(screen.getByLabelText("kind: person")).toBeInTheDocument();
    expect(screen.getByLabelText("kind: person").textContent).toBe("person");
  });

  it("omits the kind hint when data.kind is absent", () => {
    render(<ActorNode {...nodeProps({ label: "Alice" })} />);
    expect(screen.queryByLabelText(/^kind:/)).toBeNull();
  });
});

describe("SystemNode — direct render", () => {
  it("renders the label and falls back to 'System' when label is absent", () => {
    render(<SystemNode {...nodeProps({ label: "API" })} />);
    expect(screen.getByText("API")).toBeInTheDocument();
  });

  it("uses 'System' as the label fallback when data.label is undefined", () => {
    render(<SystemNode {...nodeProps({})} />);
    expect(screen.getByText("System")).toBeInTheDocument();
  });

  it("renders the optional note when supplied", () => {
    render(
      <SystemNode {...nodeProps({ label: "Cache", note: "Redis layer" })} />,
    );
    expect(screen.getByText("Redis layer")).toBeInTheDocument();
  });

  it("renders the kind hint when data.kind is supplied", () => {
    render(<SystemNode {...nodeProps({ label: "DB", kind: "data" })} />);
    expect(screen.getByLabelText("kind: data")).toBeInTheDocument();
    expect(screen.getByLabelText("kind: data").textContent).toBe("data");
  });

  it("omits the kind hint when data.kind is absent", () => {
    render(<SystemNode {...nodeProps({ label: "API" })} />);
    expect(screen.queryByLabelText(/^kind:/)).toBeNull();
  });
});
