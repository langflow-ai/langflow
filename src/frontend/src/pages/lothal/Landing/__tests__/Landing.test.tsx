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

  it("renders the hero: developer-weighted headline, pill, and marketing title", () => {
    render(<Landing />);
    expect(screen.getByText(/Build software the way/)).toBeInTheDocument();
    expect(screen.getByText("Now in early access")).toBeInTheDocument();
    expect(document.title).toBe("Lothal — software engineering, accelerated");
  });

  it("shows the larder sample once: the hero chat plus a single sample diagram", () => {
    render(<Landing />);
    expect(
      screen.getByText(
        "A tool to track bakery inventory and the week's orders.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Who places orders, and how do they reach you?"),
    ).toBeInTheDocument();
    // The hero is the only place the chat + sample diagram appear — the ladder
    // rungs use distinct visuals (PRD, ADR, gate, tree), so there's exactly one.
    const diagrams = screen.getAllByRole("img", { name: /bakery order flow/i });
    expect(diagrams).toHaveLength(1);
  });

  it("lists all six stages and flags the unbuilt ones honestly", () => {
    render(<Landing />);
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
      screen.getByText(
        "From a sentence to a shipped build — one accountable step at a time.",
      ),
    ).toBeInTheDocument();
    // Generate + Deliver aren't built yet — dimmed and tagged "coming next" in
    // the phase ribbon.
    expect(screen.getAllByText("coming next").length).toBe(2);
  });

  it("frames the reframe and both flagships (the gate + the contract tree)", () => {
    render(<Landing />);
    // The reframe / core message: accelerate, don't replace.
    expect(
      screen.getByText(/aim isn't to replace software development/i),
    ).toBeInTheDocument();
    // Flagship 1 — the enforced-validation gate (with the single V-model aside).
    expect(screen.getByText(/It has to pass/)).toBeInTheDocument();
    expect(screen.getByText(/V-model discipline/)).toBeInTheDocument();
    expect(screen.getByText("Definition of done")).toBeInTheDocument();
    // Flagship 2 — the change-aware contract/dependency tree (the centerpiece).
    expect(
      screen.getByText(
        "Change one thing, and Lothal knows everything it touches.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("↻ Re-verify downstream")).toBeInTheDocument();
    // The code-generation flagships are tagged "Coming next" (git + traceability).
    expect(screen.getAllByText("Coming next").length).toBe(1);
  });

  it("shows delivery — 'the code is yours' with the git/GitHub/export options", () => {
    render(<Landing />);
    expect(
      screen.getByText("The code is yours, and it's real."),
    ).toBeInTheDocument();
    expect(screen.getByText("Internal git")).toBeInTheDocument();
    expect(screen.getByText("Your GitHub")).toBeInTheDocument();
    expect(screen.getByText("Download whole")).toBeInTheDocument();
    // Pricing was pulled for now — the page makes no charge claim.
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/pay for verified work/i);
  });

  it("offers sign up and log in, never opening the projects app directly", () => {
    render(<Landing />);
    fireEvent.click(screen.getAllByRole("button", { name: "Sign up free" })[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/signup");
    fireEvent.click(screen.getAllByRole("button", { name: "Log in" })[0]);
    expect(mockNavigate).toHaveBeenLastCalledWith("/login");
    expect(mockNavigate).not.toHaveBeenCalledWith("/lothal");
  });

  it("scrolls to a section from the nav", () => {
    const scrollSpy = jest.fn();
    Element.prototype.scrollIntoView = scrollSpy;
    render(<Landing />);
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(scrollSpy).toHaveBeenCalled();
  });

  it("renders a v-prefixed version badge in the footer from LOTHAL_VERSION", () => {
    render(<Landing />);
    const expected = `v${LOTHAL_VERSION}`;
    expect(screen.getByText(expected)).toBeInTheDocument();
    expect(screen.getByText(expected).textContent).toMatch(/^v/);
  });

  it("renders no nautical / dockyard wording anywhere on the page", () => {
    render(<Landing />);
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/harbor|vessel|dockyard|keel|drydock/i);
  });

  it("no longer carries the 'Built on Langflow' credit (removed by request)", () => {
    render(<Landing />);
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/built on langflow/i);
  });
});
