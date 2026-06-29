import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Artifacts, Project } from "@/controllers/API/queries/lothal";

// react-markdown / remark-gfm are ESM and Jest doesn't transform node_modules;
// mock them (the repo convention) — we assert the ADR content is handed through,
// not the markdown-to-HTML rendering (that's react-markdown's own concern).
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="adr-markdown">{children}</div>
  ),
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));

// The pane reads GET /artifacts (Epic E.4) and, on approve, advances the phase.
const mockUseArtifacts = jest.fn();
const mockApproveMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useArtifacts: (...args: unknown[]) => mockUseArtifacts(...args),
  useApproveDiagram: () => ({
    mutateAsync: mockApproveMutate,
    isPending: false,
  }),
}));

// Stub the live D2 canvas (pan/zoom over an SVG); not the unit under test. The
// stub records the svg it received and fires onAnchor when clicked, so we can
// assert the diagram tab routes the SVG and forwards the anchor handler (D.7).
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
      onClick={() => onAnchor?.({ kind: "node", id: "api", label: "API" })}
    />
  ),
}));

import { ArtifactsPane } from "../ArtifactsPane";

const project = (over: Partial<Project> = {}): Project =>
  ({
    id: "p1",
    user_id: "u1",
    name: "Tide Tracker",
    phase: "ARCHITECTURE",
    prd_content: null,
    diagram_json: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  }) as Project;

const ARTIFACTS: Artifacts = {
  artifacts: {
    "adr.md": "# Decision Record\n\nWe chose a modular monolith.",
    "diagrams/context.d2": "user -> app",
    "diagrams/sequence.d2": "user -> api",
  },
  svgs: {
    "diagrams/context.d2": "<svg>context</svg>",
    "diagrams/sequence.d2": "<svg>sequence</svg>",
  },
};

const idle = {
  data: undefined,
  isLoading: false,
  isError: false,
  error: undefined,
};

const error403 = {
  response: { status: 403, data: { detail: "Not available yet." } },
};

beforeEach(() => {
  jest.clearAllMocks();
  mockApproveMutate.mockResolvedValue({ phase: "CODE_GENERATION" });
  mockUseArtifacts.mockReturnValue(idle);
});

describe("ArtifactsPane", () => {
  it("shows the phase placeholder (and does not fetch) before ARCHITECTURE", () => {
    render(<ArtifactsPane project={project({ phase: "CLARIFICATION" })} />);
    expect(
      screen.getByText("The diagram takes shape here"),
    ).toBeInTheDocument();
    // Phase-gated: the query is disabled before the architecture stage.
    expect(mockUseArtifacts).toHaveBeenCalledWith("p1", false);
  });

  it("shows a loading line while the artifacts load", () => {
    mockUseArtifacts.mockReturnValue({ ...idle, isLoading: true });
    render(<ArtifactsPane project={project()} />);
    expect(screen.getByText("Opening the architecture…")).toBeInTheDocument();
  });

  it("shows a generic failure when /artifacts errors (non-501)", () => {
    mockUseArtifacts.mockReturnValue({
      ...idle,
      isError: true,
      error: new Error("boom"),
    });
    render(<ArtifactsPane project={project()} />);
    expect(
      screen.getByText("Couldn't load the architecture"),
    ).toBeInTheDocument();
  });

  it("falls back to the placeholder while the map is still empty", () => {
    mockUseArtifacts.mockReturnValue({
      ...idle,
      data: { artifacts: {}, svgs: {} },
    });
    render(<ArtifactsPane project={project()} />);
    expect(screen.getByText("Designing the architecture")).toBeInTheDocument();
  });

  it("renders the ADR tab as markdown by default", () => {
    mockUseArtifacts.mockReturnValue({ ...idle, data: ARTIFACTS });
    render(<ArtifactsPane project={project()} />);
    // The ADR leads; its markdown source is handed to the renderer.
    const adr = screen.getByTestId("adr-markdown");
    expect(adr).toHaveTextContent("# Decision Record");
    expect(adr).toHaveTextContent("We chose a modular monolith.");
    // A tab per artifact, in canonical order — the ADR active by default.
    expect(
      screen.getByRole("tab", { name: "Decision Record" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Context" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Sequence" })).toBeInTheDocument();
  });

  it("switches to a diagram tab and renders its server SVG on the canvas", () => {
    mockUseArtifacts.mockReturnValue({ ...idle, data: ARTIFACTS });
    render(<ArtifactsPane project={project()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Context" }));
    expect(screen.getByTestId("d2-canvas")).toHaveAttribute(
      "data-svg",
      "<svg>context</svg>",
    );
  });

  it("shows NotReady on a diagram tab whose SVG couldn't be rendered", () => {
    mockUseArtifacts.mockReturnValue({
      ...idle,
      data: {
        artifacts: { "diagrams/sequence.d2": "user -> api" },
        svgs: { "diagrams/sequence.d2": null },
      },
    });
    render(<ArtifactsPane project={project()} />);
    // Single diagram, no ADR → that diagram tab is active; null svg → NotReady.
    expect(
      screen.getByText("Couldn't render this diagram"),
    ).toBeInTheDocument();
  });

  it("reports the active artifact up as the tab changes", () => {
    const onActive = jest.fn();
    mockUseArtifacts.mockReturnValue({ ...idle, data: ARTIFACTS });
    render(
      <ArtifactsPane project={project()} onActiveArtifactChange={onActive} />,
    );
    // Defaults to the ADR.
    expect(onActive).toHaveBeenCalledWith("adr.md");
    fireEvent.click(screen.getByRole("tab", { name: "Sequence" }));
    expect(onActive).toHaveBeenLastCalledWith("diagrams/sequence.d2");
  });

  it("forwards a double-clicked diagram element to onAnchor", () => {
    const onAnchor = jest.fn();
    mockUseArtifacts.mockReturnValue({ ...idle, data: ARTIFACTS });
    render(<ArtifactsPane project={project()} onAnchor={onAnchor} />);
    fireEvent.click(screen.getByRole("tab", { name: "Context" }));
    fireEvent.click(screen.getByTestId("d2-canvas"));
    expect(onAnchor).toHaveBeenCalledWith({
      kind: "node",
      id: "api",
      label: "API",
    });
  });

  it("offers Approve in ARCHITECTURE with a non-empty map and approves on click", async () => {
    mockUseArtifacts.mockReturnValue({ ...idle, data: ARTIFACTS });
    render(<ArtifactsPane project={project()} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Approve & build prototype" }),
    );
    await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledTimes(1));
  });

  it("does not offer Approve once past ARCHITECTURE (code phase)", () => {
    mockUseArtifacts.mockReturnValue({ ...idle, data: ARTIFACTS });
    render(<ArtifactsPane project={project({ phase: "CODE_GENERATION" })} />);
    expect(
      screen.queryByRole("button", { name: "Approve & build prototype" }),
    ).not.toBeInTheDocument();
  });

  it("treats a 403 phase gate as a recoverable not-ready, not a hard error", () => {
    // The query returns 403 if read just before the phase flips; the pane keys
    // its generic load failure off any error (NotReady), never a crash.
    mockUseArtifacts.mockReturnValue({
      ...idle,
      isError: true,
      error: error403,
    });
    render(<ArtifactsPane project={project()} />);
    expect(
      screen.getByText("Couldn't load the architecture"),
    ).toBeInTheDocument();
  });
});
