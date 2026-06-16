import { fireEvent, render, screen } from "@testing-library/react";
import type {
  DiagramEdge,
  DiagramNode,
} from "@/controllers/API/queries/lothal";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

// Stub the real ReactFlow canvas — it needs layout/ResizeObserver and isn't
// the unit under test. We only assert the landing feeds it the sample graph.
jest.mock("../../components/DiagramCanvas", () => ({
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

import { LOTHAL_VERSION } from "../../components";
import Landing from "../index";

describe("Lothal Landing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the design's hero: headline, pill, and marketing title", () => {
    render(<Landing />);
    expect(screen.getByText(/Build software the way/)).toBeInTheDocument();
    expect(screen.getByText("Now in early access")).toBeInTheDocument();
    expect(document.title).toBe("Lothal — build software by describing it");
  });

  it("shows the larder sample: bakery chat plus two live canvas renders", () => {
    render(<Landing />);
    expect(
      screen.getByText(
        "A tool to track bakery inventory and the week's orders.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Who places orders, and how do they reach you?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Phone + a webpage")).toBeInTheDocument();
    const canvases = screen.getAllByTestId("diagram-canvas");
    expect(canvases).toHaveLength(2);
    for (const canvas of canvases) {
      expect(canvas).toHaveAttribute("data-nodes", "4");
      expect(canvas).toHaveAttribute("data-edges", "4");
    }
  });

  it("lists all five steps from the shared phase metadata", () => {
    render(<Landing />);
    for (const label of [
      "Clarify",
      "Sketch",
      "Refine",
      "Generate",
      "Deliver",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(
      screen.getByText("Five steps from a sentence to a codebase."),
    ).toBeInTheDocument();
  });

  it("shows the principles, canvas showcase, and delivery sections", () => {
    render(<Landing />);
    expect(screen.getByText("No assumptions")).toBeInTheDocument();
    expect(screen.getByText("Diagram before code")).toBeInTheDocument();
    expect(screen.getByText("You stay in control")).toBeInTheDocument();
    expect(
      screen.getByText("A real diagram, not a black box."),
    ).toBeInTheDocument();
    expect(screen.getByText("Internal Git")).toBeInTheDocument();
    expect(screen.getByText("Download ZIP")).toBeInTheDocument();
  });

  it("offers sign up and log in, never opening the projects app directly", () => {
    render(<Landing />);
    // Primary CTA creates an account…
    fireEvent.click(screen.getAllByRole("button", { name: "Sign up free" })[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/signup");
    // …and the secondary CTA signs an existing user in.
    fireEvent.click(screen.getAllByRole("button", { name: "Log in" })[0]);
    expect(mockNavigate).toHaveBeenLastCalledWith("/login");
    // The landing must never jump straight into the (auth-guarded) projects app.
    expect(mockNavigate).not.toHaveBeenCalledWith("/lothal");
  });

  it("scrolls to a section from the nav", () => {
    const scrollSpy = jest.fn();
    Element.prototype.scrollIntoView = scrollSpy;
    render(<Landing />);
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(scrollSpy).toHaveBeenCalled();
  });

  // --- Version badge --------------------------------------------------------

  it("renders a v-prefixed version badge in the footer from LOTHAL_VERSION", () => {
    render(<Landing />);
    // The footer renders `v{LOTHAL_VERSION}` in a mono span.  Assert that the
    // rendered text starts with 'v' and equals the constant so neither the
    // prefix nor the constant value can drift independently.
    const expected = `v${LOTHAL_VERSION}`;
    expect(screen.getByText(expected)).toBeInTheDocument();
    expect(screen.getByText(expected).textContent).toMatch(/^v/);
  });

  // --- Voice guard + Langflow credit ----------------------------------------

  it("renders no nautical / dockyard wording anywhere on the page", () => {
    render(<Landing />);
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/harbor|vessel|dockyard|keel|drydock/i);
  });

  it("displays the 'Built on Langflow' credit in the footer", () => {
    render(<Landing />);
    // The footer credit is lowercase "built on langflow" in source; match
    // case-insensitively so a capitalisation change doesn't create a false red.
    expect(screen.getByText(/built on langflow/i)).toBeInTheDocument();
  });
});
