import { render, screen } from "@testing-library/react";
import type {
  Diagram,
  DiagramEdge,
  DiagramNode,
  Project,
} from "@/controllers/API/queries/lothal";

// Capture the diagram-query call so we can assert the phase gate (no fetch
// before DIAGRAM_GENERATION).
const mockUseDiagram = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useDiagram: (...args: unknown[]) => mockUseDiagram(...args),
}));

// Stub the real ReactFlow canvas — it needs layout/ResizeObserver and isn't the
// unit under test. We only care that CanvasSurface routes to it with the payload.
jest.mock("../DiagramCanvas", () => ({
  DiagramCanvas: ({
    nodes,
    edges,
  }: {
    nodes: DiagramNode[];
    edges: DiagramEdge[];
  }) => (
    <div
      data-testid="diagram-canvas"
      data-nodes={nodes.length}
      data-edges={edges.length}
    />
  ),
}));

import { CanvasSurface } from "../CanvasSurface";

const project = (over: Partial<Project> = {}): Project =>
  ({
    id: "p1",
    user_id: "u1",
    name: "Tide Tracker",
    phase: "CLARIFICATION",
    prd_content: null,
    diagram_json: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  }) as Project;

const error501 = {
  response: {
    status: 501,
    data: {
      detail: "The diagram endpoint isn't built yet.",
      status: "not_implemented",
    },
  },
};

const diagram = (over: Partial<Diagram> = {}): Diagram => ({
  mermaid: null,
  nodes: [],
  edges: [],
  ...over,
});

const sampleNodes: DiagramNode[] = [
  {
    id: "u",
    type: "actorNode",
    position: { x: 0, y: 0 },
    data: { label: "User" },
  },
  {
    id: "s",
    type: "systemNode",
    position: { x: 0, y: 0 },
    data: { label: "API" },
  },
];
const sampleEdges: DiagramEdge[] = [
  { id: "e1", source: "u", target: "s", label: "go", data: { order: 1 } },
];

beforeEach(() => {
  jest.clearAllMocks();
  mockUseDiagram.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    error: undefined,
  });
});

describe("CanvasSurface", () => {
  it("shows the placeholder and does NOT fetch during CLARIFICATION", () => {
    render(<CanvasSurface project={project({ phase: "CLARIFICATION" })} />);
    expect(
      screen.getByText("The diagram takes shape here"),
    ).toBeInTheDocument();
    // The phase gate is the second arg to useDiagram — false means no request.
    expect(mockUseDiagram).toHaveBeenCalledWith("p1", false);
  });

  it("enables the fetch from DIAGRAM_GENERATION onward", () => {
    render(
      <CanvasSurface project={project({ phase: "DIAGRAM_GENERATION" })} />,
    );
    expect(mockUseDiagram).toHaveBeenCalledWith("p1", true);
  });

  it("shows a loading state while the diagram loads", () => {
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    render(
      <CanvasSurface project={project({ phase: "DIAGRAM_GENERATION" })} />,
    );
    expect(screen.getByText("Opening the canvas…")).toBeInTheDocument();
  });

  it("shows NotReady (with the 501 detail) when /diagram is a stub", () => {
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: error501,
    });
    render(
      <CanvasSurface project={project({ phase: "DIAGRAM_GENERATION" })} />,
    );
    expect(screen.getByText("The canvas isn't live yet")).toBeInTheDocument();
    expect(
      screen.getByText("The diagram endpoint isn't built yet."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("diagram-canvas")).not.toBeInTheDocument();
  });

  it("shows a generic NotReady on a non-501 failure", () => {
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
    });
    render(
      <CanvasSurface project={project({ phase: "DIAGRAM_GENERATION" })} />,
    );
    expect(screen.getByText("Couldn't load the diagram")).toBeInTheDocument();
  });

  it("shows the placeholder when the endpoint is live but the diagram is empty", () => {
    mockUseDiagram.mockReturnValue({
      data: diagram({ nodes: [], edges: [] }),
      isLoading: false,
      isError: false,
    });
    render(
      <CanvasSurface project={project({ phase: "DIAGRAM_GENERATION" })} />,
    );
    expect(screen.getByText("Sketching the diagram")).toBeInTheDocument();
    expect(screen.queryByTestId("diagram-canvas")).not.toBeInTheDocument();
  });

  it("renders the canvas with the diagram's node/edge counts when present", () => {
    mockUseDiagram.mockReturnValue({
      data: diagram({ nodes: sampleNodes, edges: sampleEdges }),
      isLoading: false,
      isError: false,
    });
    render(
      <CanvasSurface project={project({ phase: "DIAGRAM_REFINEMENT" })} />,
    );
    const canvas = screen.getByTestId("diagram-canvas");
    expect(canvas).toHaveAttribute("data-nodes", "2");
    expect(canvas).toHaveAttribute("data-edges", "1");
  });
});
