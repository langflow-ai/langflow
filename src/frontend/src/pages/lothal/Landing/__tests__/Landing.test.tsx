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

import useAuthStore from "@/stores/authStore";
import Landing from "../index";

function setAuth(state: { isAuthenticated: boolean; autoLogin: boolean }) {
  useAuthStore.setState(state);
}

describe("Lothal Landing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setAuth({ isAuthenticated: false, autoLogin: false });
  });

  it("renders the design's hero: headline, pill, and marketing title", () => {
    render(<Landing />);
    expect(screen.getByText(/Build software the way/)).toBeInTheDocument();
    expect(
      screen.getByText("Built on Langflow · now in early access"),
    ).toBeInTheDocument();
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

  it("sends anonymous visitors to login with the lothal redirect", () => {
    render(<Landing />);
    fireEvent.click(
      screen.getAllByRole("button", { name: "Start building free" })[0],
    );
    expect(mockNavigate).toHaveBeenCalledWith("/login?redirect=/lothal");
    fireEvent.click(screen.getAllByRole("button", { name: "Sign in" })[0]);
    expect(mockNavigate).toHaveBeenLastCalledWith("/login?redirect=/lothal");
  });

  it("sends authenticated users straight to the dashboard, without Sign in", () => {
    setAuth({ isAuthenticated: true, autoLogin: false });
    render(<Landing />);
    expect(
      screen.queryByRole("button", { name: "Sign in" }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getAllByRole("button", { name: "Open dashboard" })[0],
    );
    expect(mockNavigate).toHaveBeenCalledWith("/lothal");
  });

  it("treats auto-login deployments as authenticated", () => {
    setAuth({ isAuthenticated: false, autoLogin: true });
    render(<Landing />);
    expect(
      screen.getAllByRole("button", { name: "Open dashboard" }).length,
    ).toBeGreaterThan(0);
  });

  it("scrolls to a section from the nav", () => {
    const scrollSpy = jest.fn();
    Element.prototype.scrollIntoView = scrollSpy;
    render(<Landing />);
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(scrollSpy).toHaveBeenCalled();
  });
});
