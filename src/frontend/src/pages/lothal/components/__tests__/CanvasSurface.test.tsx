import { render, screen } from "@testing-library/react";
import type { Diagram, Project } from "@/controllers/API/queries/lothal";

// Capture the diagram-query call so we can assert the phase gate (no fetch
// before ARCHITECTURE).
const mockUseDiagram = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useDiagram: (...args: unknown[]) => mockUseDiagram(...args),
}));

// Stub the live D2 canvas — it drives DOM layout/pointer gestures and isn't the
// unit under test. We care that CanvasSurface routes to it with the SVG and
// forwards the onAnchor handler (a double-click → chip; D.7). The stub fires
// onAnchor when its button is clicked so we can assert the wiring.
jest.mock("../D2Canvas", () => ({
  D2Canvas: ({
    svg,
    onAnchor,
  }: {
    svg: string;
    onAnchor?: (a: unknown) => void;
  }) => (
    <button
      type="button"
      data-testid="d2-canvas"
      data-svg={svg}
      data-has-onanchor={onAnchor ? "yes" : "no"}
      onClick={() => onAnchor?.({ kind: "node", id: "checkout" })}
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
  d2: null,
  svg: null,
  ...over,
});

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

  it("enables the fetch from ARCHITECTURE onward", () => {
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(mockUseDiagram).toHaveBeenCalledWith("p1", true);
  });

  it("shows a loading state while the diagram loads", () => {
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(screen.getByText("Opening the canvas…")).toBeInTheDocument();
  });

  it("shows NotReady (with the 501 detail) when /diagram is a stub", () => {
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: error501,
    });
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(screen.getByText("The canvas isn't live yet")).toBeInTheDocument();
    expect(
      screen.getByText("The diagram endpoint isn't built yet."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("d2-canvas")).not.toBeInTheDocument();
  });

  it("shows a generic NotReady on a non-501 failure", () => {
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
    });
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(screen.getByText("Couldn't load the diagram")).toBeInTheDocument();
  });

  it("shows the placeholder when the endpoint is live but no D2 has been emitted", () => {
    mockUseDiagram.mockReturnValue({
      data: diagram({ d2: null, svg: null }),
      isLoading: false,
      isError: false,
    });
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(screen.getByText("Designing the architecture")).toBeInTheDocument();
    expect(screen.queryByTestId("d2-canvas")).not.toBeInTheDocument();
  });

  it("shows NotReady when D2 exists but the server couldn't render an SVG", () => {
    mockUseDiagram.mockReturnValue({
      data: diagram({ d2: "a -> b", svg: null }),
      isLoading: false,
      isError: false,
    });
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(screen.getByText("Couldn't render the diagram")).toBeInTheDocument();
    expect(screen.queryByTestId("d2-canvas")).not.toBeInTheDocument();
  });

  it("renders the D2 canvas with the server SVG when present", () => {
    mockUseDiagram.mockReturnValue({
      data: diagram({ d2: "a -> b", svg: "<svg>hi</svg>" }),
      isLoading: false,
      isError: false,
    });
    render(<CanvasSurface project={project({ phase: "ARCHITECTURE" })} />);
    expect(screen.getByTestId("d2-canvas")).toHaveAttribute(
      "data-svg",
      "<svg>hi</svg>",
    );
  });

  it("forwards onAnchor through to the D2 canvas (D.7)", () => {
    const onAnchor = jest.fn();
    mockUseDiagram.mockReturnValue({
      data: diagram({ d2: "a -> b", svg: "<svg>hi</svg>" }),
      isLoading: false,
      isError: false,
    });
    render(
      <CanvasSurface
        project={project({ phase: "ARCHITECTURE" })}
        onAnchor={onAnchor}
      />,
    );
    const canvas = screen.getByTestId("d2-canvas");
    expect(canvas).toHaveAttribute("data-has-onanchor", "yes");
    canvas.click();
    expect(onAnchor).toHaveBeenCalledWith({ kind: "node", id: "checkout" });
  });
});
