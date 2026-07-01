import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

// <SampleDiagram> (Epic D.15, replacing the old xyflow <DiagramCanvas>) is a
// plain static SVG — no layout/ResizeObserver dependency — so it renders fine in
// jsdom and needs no mock.

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

  it("shows the larder sample: bakery chat plus the hero sample-diagram render", () => {
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
    // The hero renders the <SampleDiagram> (an accessible SVG figure); the
    // verification band now shows a plan-node mock instead of a second diagram.
    const diagrams = screen.getAllByRole("img", {
      name: /bakery order flow/i,
    });
    expect(diagrams).toHaveLength(1);
  });

  it("lists all six stages from the shared phase metadata", () => {
    render(<Landing />);
    // "Design" and "Plan" also appear in the hero overlay / plan-node mock, so
    // assert presence rather than uniqueness.
    for (const label of [
      "Clarify",
      "Design",
      "Prototype",
      "Plan",
      "Generate",
      "Deliver",
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(
      screen.getByText("Six stages, from a sentence to a build-ready plan."),
    ).toBeInTheDocument();
    // Generate + Deliver are not built yet — flagged honestly.
    expect(screen.getAllByText("Coming next").length).toBe(2);
  });

  it("shows the principles, verification band, and artifacts sections", () => {
    render(<Landing />);
    expect(screen.getByText("Nothing built on a guess")).toBeInTheDocument();
    expect(screen.getByText("'Done' is defined first")).toBeInTheDocument();
    expect(screen.getByText("You hold every gate")).toBeInTheDocument();
    // The differentiator band (verification-driven planning).
    expect(screen.getByText("Proven before it composes.")).toBeInTheDocument();
    // The artifacts you accumulate (real, shipped — not the old code-delivery stubs).
    expect(screen.getByText("A clear spec")).toBeInTheDocument();
    expect(screen.getByText("A verification-ready plan")).toBeInTheDocument();
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
