import { fireEvent, render, screen } from "@testing-library/react";
import { LothalSurface, useLothalTheme } from "../../theme/LothalSurface";
import {
  Button,
  EmptyHint,
  isNotImplemented,
  LothalMark,
  NotReady,
  notImplementedDetail,
  PHASES,
  PhaseStepper,
  phaseIndex,
  StatusDot,
  TopBar,
} from "../index";

describe("phases", () => {
  it("orders the five phases and resolves indices", () => {
    expect(PHASES.map((p) => p.id)).toEqual([
      "CLARIFICATION",
      "DIAGRAM_GENERATION",
      "DIAGRAM_REFINEMENT",
      "CODE_GENERATION",
      "DONE",
    ]);
    expect(phaseIndex("DIAGRAM_REFINEMENT")).toBe(2);
    expect(phaseIndex("UNKNOWN")).toBe(-1);
  });
});

describe("Button", () => {
  it("renders children and fires onClick when enabled", () => {
    const onClick = jest.fn();
    render(
      <Button variant="accent" onClick={onClick}>
        Launch
      </Button>,
    );
    fireEvent.click(screen.getByText("Launch"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick when disabled", () => {
    const onClick = jest.fn();
    render(
      <Button disabled onClick={onClick}>
        Nope
      </Button>,
    );
    fireEvent.click(screen.getByText("Nope"));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("StatusDot", () => {
  it("shows the verb for the phase", () => {
    render(<StatusDot phase="CODE_GENERATION" />);
    expect(screen.getByText("generating")).toBeInTheDocument();
  });

  it("falls back to the clarifying verb for an unknown phase", () => {
    render(<StatusDot phase="WHATEVER" />);
    expect(screen.getByText("clarifying")).toBeInTheDocument();
  });
});

describe("PhaseStepper", () => {
  it("renders all phase labels in breadcrumb form", () => {
    render(<PhaseStepper phase="DIAGRAM_REFINEMENT" variant="breadcrumb" />);
    for (const label of [
      "Clarify",
      "Sketch",
      "Refine",
      "Generate",
      "Deliver",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders the NN / 05 counter in pill form", () => {
    render(<PhaseStepper phase="DIAGRAM_REFINEMENT" variant="pill" />);
    expect(screen.getByText("03 / 05")).toBeInTheDocument();
  });

  it("marks completed phases with a check in the default stepper variant", () => {
    // Active phase is index 2 (Refine), so Clarify + Sketch are done.
    render(<PhaseStepper phase="DIAGRAM_REFINEMENT" />);
    expect(screen.getAllByText("✓")).toHaveLength(2);
    expect(screen.getByText("Refine")).toBeInTheDocument();
    expect(screen.getByText("Deliver")).toBeInTheDocument();
  });
});

describe("TopBar", () => {
  it("renders the left, center, and right slots", () => {
    render(
      <TopBar
        left={<span>left-slot</span>}
        center={<span>center-slot</span>}
        right={<span>right-slot</span>}
      />,
    );
    expect(screen.getByText("left-slot")).toBeInTheDocument();
    expect(screen.getByText("center-slot")).toBeInTheDocument();
    expect(screen.getByText("right-slot")).toBeInTheDocument();
  });
});

describe("LothalMark", () => {
  it("renders an accessible paper-boat svg", () => {
    render(<LothalMark size={28} />);
    expect(screen.getByRole("img", { name: "Lothal" })).toBeInTheDocument();
  });
});

describe("EmptyHint", () => {
  it("renders title, sub, and kbd", () => {
    render(<EmptyHint title="Nothing here" sub="Add one" kbd="N" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Add one")).toBeInTheDocument();
    expect(screen.getByText("N")).toBeInTheDocument();
  });
});

describe("NotReady — structured 501 detection", () => {
  const axios501 = {
    response: {
      status: 501,
      data: { detail: "Not built yet.", status: "not_implemented" },
    },
  };

  it("isNotImplemented matches a 501 status and a not_implemented body", () => {
    expect(isNotImplemented(axios501)).toBe(true);
    expect(isNotImplemented({ data: { status: "not_implemented" } })).toBe(
      true,
    );
    expect(isNotImplemented({ response: { status: 500 } })).toBe(false);
    expect(isNotImplemented(null)).toBe(false);
    expect(isNotImplemented("boom")).toBe(false);
  });

  it("notImplementedDetail extracts the message or uses the fallback", () => {
    expect(notImplementedDetail(axios501)).toBe("Not built yet.");
    expect(notImplementedDetail({}, "fallback")).toBe("fallback");
  });

  it("renders the 501 detail message", () => {
    render(<NotReady error={axios501} />);
    expect(screen.getByText("Not ready yet")).toBeInTheDocument();
    expect(screen.getByText("Not built yet.")).toBeInTheDocument();
  });
});

describe("LothalSurface", () => {
  it("applies theme + density data attributes and renders children", () => {
    const { container } = render(
      <LothalSurface defaultTheme="dark" defaultDensity="compact">
        <span>inside</span>
      </LothalSurface>,
    );
    const surface = container.querySelector(".lothal-surface");
    expect(surface).not.toBeNull();
    expect(surface).toHaveAttribute("data-theme", "dark");
    expect(surface).toHaveAttribute("data-density", "compact");
    expect(screen.getByText("inside")).toBeInTheDocument();
  });

  it("toggleTheme flips light <-> dark via the hook", () => {
    function Probe() {
      const { theme, toggleTheme } = useLothalTheme();
      return (
        <button type="button" onClick={toggleTheme}>
          {theme}
        </button>
      );
    }
    render(
      <LothalSurface defaultTheme="light">
        <Probe />
      </LothalSurface>,
    );
    expect(screen.getByRole("button")).toHaveTextContent("light");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveTextContent("dark");
  });
});
