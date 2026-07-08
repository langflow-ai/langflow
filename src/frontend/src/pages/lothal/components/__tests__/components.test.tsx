import { fireEvent, render, screen } from "@testing-library/react";
import { LothalSurface, useLothalTheme } from "../../theme/LothalSurface";
import {
  AssistantQuestion,
  Button,
  CanvasPlaceholder,
  ChatBubble,
  ChatDock,
  CodeView,
  EmptyHint,
  highlightTokens,
  isNotImplemented,
  LothalMark,
  languageFromPath,
  NotReady,
  notImplementedDetail,
  PHASES,
  PhaseStepper,
  phaseIndex,
  StatusDot,
  SystemBlock,
  TopBar,
  uiPhase,
} from "../index";

describe("phases", () => {
  it("orders the six phases and resolves indices", () => {
    expect(PHASES.map((p) => p.id)).toEqual([
      "CLARIFICATION",
      "ARCHITECTURE",
      "PROTOTYPE",
      "PLAN",
      "REVIEW",
      "DONE",
    ]);
    expect(phaseIndex("ARCHITECTURE")).toBe(1);
    expect(phaseIndex("PROTOTYPE")).toBe(2);
    expect(phaseIndex("PLAN")).toBe(3);
    expect(phaseIndex("UNKNOWN")).toBe(-1);
  });

  it("maps the backend CODE_GENERATION phase onto the REVIEW UI stage", () => {
    // Part B: codegen is a backend stage launched from the Plan pane; the UI
    // presents it as Review. Every other phase passes through unchanged.
    expect(uiPhase("CODE_GENERATION")).toBe("REVIEW");
    expect(uiPhase("PLAN")).toBe("PLAN");
    expect(phaseIndex(uiPhase("CODE_GENERATION"))).toBe(4);
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
  it("shows the verb for the phase (raw backend phase maps to Review)", () => {
    render(<StatusDot phase="CODE_GENERATION" />);
    expect(screen.getByText("reviewing")).toBeInTheDocument();
  });

  it("falls back to the clarifying verb for an unknown phase", () => {
    render(<StatusDot phase="WHATEVER" />);
    expect(screen.getByText("clarifying")).toBeInTheDocument();
  });
});

describe("PhaseStepper", () => {
  it("renders all phase labels in breadcrumb form", () => {
    render(<PhaseStepper phase="ARCHITECTURE" variant="breadcrumb" />);
    for (const label of [
      "Clarify",
      "Design",
      "Prototype",
      "Plan",
      "Review",
      "Deliver",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders the NN / 06 counter in pill form", () => {
    render(<PhaseStepper phase="ARCHITECTURE" variant="pill" />);
    expect(screen.getByText("02 / 06")).toBeInTheDocument();
  });

  it("marks completed phases with a check in the default stepper variant", () => {
    // Active phase is index 1 (Design), so only Clarify is done.
    render(<PhaseStepper phase="ARCHITECTURE" />);
    expect(screen.getAllByText("✓")).toHaveLength(1);
    expect(screen.getByText("Design")).toBeInTheDocument();
    expect(screen.getByText("Deliver")).toBeInTheDocument();
  });

  it("makes stages up to currentPhase clickable and reports the phase id", () => {
    const onSelect = jest.fn();
    render(
      <PhaseStepper
        phase="ARCHITECTURE"
        currentPhase="PLAN"
        onSelect={onSelect}
      />,
    );
    // Reachable stages (index <= the live PLAN phase) render as buttons.
    fireEvent.click(screen.getByTitle("View the Design stage"));
    expect(onSelect).toHaveBeenCalledWith("ARCHITECTURE");
    fireEvent.click(screen.getByTitle("View the Plan stage"));
    expect(onSelect).toHaveBeenLastCalledWith("PLAN");
    // Future stages (beyond the live phase) are NOT navigable.
    expect(screen.queryByTitle("View the Generate stage")).toBeNull();
    expect(screen.queryByTitle("View the Deliver stage")).toBeNull();
  });

  it("keys done-marks and the live dot off currentPhase, not the viewed phase", () => {
    const { rerender } = render(
      <PhaseStepper phase="ARCHITECTURE" currentPhase="PLAN" />,
    );
    // done = every stage before the live phase: Clarify, Design, Prototype.
    expect(screen.getAllByText("✓")).toHaveLength(3);
    // Without onSelect even reachable stages aren't clickable.
    expect(screen.queryByTitle("View the Design stage")).toBeNull();
    // Viewing an earlier stage marks the live one with the "Current stage" dot.
    expect(screen.getByTitle("Current stage")).toBeInTheDocument();
    // Viewing the live stage itself → no separate dot (active === live).
    rerender(<PhaseStepper phase="PLAN" currentPhase="PLAN" />);
    expect(screen.queryByTitle("Current stage")).toBeNull();
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
  it("injects the Lothal fonts once, on mount", () => {
    // The fonts left index.html so non-lothal pages never load them; the
    // surface injects the stylesheet link exactly once, even when several
    // surfaces mount.
    render(
      <LothalSurface>
        <LothalSurface>
          <span>nested</span>
        </LothalSurface>
      </LothalSurface>,
    );
    const links = document.querySelectorAll("#lothal-fonts");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute(
      "href",
      expect.stringContaining("Instrument+Serif"),
    );
  });

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

describe("ChatBubble", () => {
  it("labels the sender by role and renders the content", () => {
    render(<ChatBubble role="USER" content="hello there" />);
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("hello there")).toBeInTheDocument();
  });

  it("attaches the streaming caret only when streaming", () => {
    const { rerender, container } = render(
      <ChatBubble role="ASSISTANT" content="typing" />,
    );
    expect(screen.getByText("Lothal")).toBeInTheDocument();
    expect(container.querySelector(".caret")).toBeNull();
    rerender(<ChatBubble role="ASSISTANT" content="typing" streaming />);
    expect(container.querySelector(".caret")).not.toBeNull();
  });
});

describe("AssistantQuestion", () => {
  it("renders a chip per suggestion and reports the picked one", () => {
    const onPick = jest.fn();
    render(
      <AssistantQuestion suggestions={["Casual", "Serious"]} onPick={onPick} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Serious" }));
    expect(onPick).toHaveBeenCalledWith("Serious");
  });

  it("renders nothing when there are no suggestions", () => {
    const { container } = render(
      <AssistantQuestion suggestions={[]} onPick={jest.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("does not fire onPick while disabled", () => {
    const onPick = jest.fn();
    render(<AssistantQuestion suggestions={["A"]} onPick={onPick} disabled />);
    fireEvent.click(screen.getByRole("button", { name: "A" }));
    expect(onPick).not.toHaveBeenCalled();
  });

  it("renders duplicate suggestions without React key collisions", () => {
    // LLM-produced suggestion arrays can repeat a string; every chip must
    // still render, with no duplicate-key warning from React.
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(
        <AssistantQuestion
          suggestions={["Yes", "No", "Yes"]}
          onPick={jest.fn()}
        />,
      );
      expect(screen.getAllByRole("button")).toHaveLength(3);
      const keyWarnings = errorSpy.mock.calls.filter((args) =>
        String(args[0]).includes("same key"),
      );
      expect(keyWarnings).toHaveLength(0);
    } finally {
      errorSpy.mockRestore();
    }
  });
});

describe("SystemBlock", () => {
  it("renders the kicker and the transition text", () => {
    render(<SystemBlock>Requirements clear — sketching</SystemBlock>);
    expect(screen.getByText("Phase")).toBeInTheDocument();
    expect(
      screen.getByText("Requirements clear — sketching"),
    ).toBeInTheDocument();
  });
});

describe("ChatDock", () => {
  it("sends on Enter and inserts a newline on Shift+Enter", () => {
    const onSend = jest.fn();
    render(
      <ChatDock value="a tide app" onChange={jest.fn()} onSend={onSend} />,
    );
    const input = screen.getByLabelText("Message");
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("does not send when the value is blank", () => {
    const onSend = jest.fn();
    render(<ChatDock value="   " onChange={jest.fn()} onSend={onSend} />);
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("CanvasPlaceholder", () => {
  it("shows phase-aware copy for clarification", () => {
    render(<CanvasPlaceholder phase="CLARIFICATION" />);
    expect(
      screen.getByText("The diagram takes shape here"),
    ).toBeInTheDocument();
  });

  it("falls back to a neutral message for an unmapped phase", () => {
    render(<CanvasPlaceholder phase="DONE" />);
    expect(screen.getByText("Nothing on the canvas yet")).toBeInTheDocument();
  });
});

describe("syntax", () => {
  it("maps file extensions to a coarse language id", () => {
    expect(languageFromPath("app/main.ts")).toBe("ts");
    expect(languageFromPath("Component.tsx")).toBe("ts");
    expect(languageFromPath("service.py")).toBe("py");
    expect(languageFromPath("config.json")).toBe("json");
    expect(languageFromPath("styles.css")).toBe("css");
    expect(languageFromPath("README.md")).toBe("md");
    expect(languageFromPath("Makefile")).toBe("text");
    expect(languageFromPath("weird.unknownext")).toBe("text");
  });

  it("tokenizes comments, strings, and keywords", () => {
    const tokens = highlightTokens('const x = "hi"; // note', "ts");
    expect(tokens).toContainEqual({ text: "const", type: "keyword" });
    expect(tokens).toContainEqual({ text: '"hi"', type: "string" });
    expect(tokens).toContainEqual({ text: "// note", type: "comment" });
  });

  it("is lossless — joining the token texts reproduces the input", () => {
    const code = 'def greet(name):\n    return f"hi {name}"  # comment\n';
    const tokens = highlightTokens(code, "py");
    expect(tokens.map((t) => t.text).join("")).toBe(code);
    expect(tokens).toContainEqual({ text: "def", type: "keyword" });
  });
});

describe("CodeView", () => {
  const FILES = [
    { path: "src/app.py", content: 'name = "alpha"\n' },
    { path: "src/util/helpers.py", content: 'value = "bravo"\n' },
    { path: "README.md", content: "# Readme heading\n" },
  ];

  it("renders the file tree and shows the first file by default", () => {
    render(<CodeView files={FILES} />);
    // Tree shows folders and files.
    expect(screen.getByText("src")).toBeInTheDocument();
    expect(screen.getByText("util")).toBeInTheDocument();
    expect(screen.getByText("app.py")).toBeInTheDocument();
    expect(screen.getByText("README.md")).toBeInTheDocument();
    // First leaf (src/util/helpers.py) is shown by default.
    expect(screen.getByText('"bravo"')).toBeInTheDocument();
  });

  it("shows a file's content when it's selected in the tree", () => {
    render(<CodeView files={FILES} />);
    fireEvent.click(screen.getByText("app.py"));
    expect(screen.getByText('"alpha"')).toBeInTheDocument();
  });

  it("summarizes the generation and renders disabled delivery buttons", () => {
    render(<CodeView files={FILES} />);
    expect(screen.getByText("Generated")).toBeInTheDocument();
    expect(screen.getByText("3 files")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download ZIP" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Push to GitHub" }),
    ).toBeDisabled();
  });

  it("renders a defensive empty state when there are no files", () => {
    render(<CodeView files={[]} />);
    expect(screen.getByText("No files yet")).toBeInTheDocument();
  });

  it("collapses and expands a folder in the tree", () => {
    render(<CodeView files={FILES} />);
    // `app.py` lives under `src` and isn't the default tab, so it appears once.
    expect(screen.getByText("app.py")).toBeInTheDocument();
    fireEvent.click(screen.getByText("src")); // collapse
    expect(screen.queryByText("app.py")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("src")); // expand
    expect(screen.getByText("app.py")).toBeInTheDocument();
  });

  it("falls back to another open tab when the active tab is closed", () => {
    render(<CodeView files={FILES} />);
    // Open two tabs by selecting two files; README.md ends up active.
    fireEvent.click(screen.getByText("app.py"));
    fireEvent.click(screen.getByText("README.md"));
    expect(
      screen.getByRole("button", { name: "Close README.md" }),
    ).toBeInTheDocument();
    // Closing the active tab falls back to the remaining open tab (app.py).
    fireEvent.click(screen.getByRole("button", { name: "Close README.md" }));
    expect(
      screen.queryByRole("button", { name: "Close README.md" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText('"alpha"')).toBeInTheDocument();
  });

  // Regression guard (from the code review): closing the sole auto-opened tab
  // must actually close it (previously it immediately reappeared).
  it("closing the sole auto-opened tab actually closes it", () => {
    // Input: a single file auto-opens as one tab with a close button.
    render(<CodeView files={[{ path: "only.py", content: "x = 1\n" }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Close only.py" }));
    // Expected: the tab (and its close button) is gone.
    expect(
      screen.queryByRole("button", { name: "Close only.py" }),
    ).not.toBeInTheDocument();
  });

  // Duplicate-key regression: a payload where a segment is both a file and a
  // directory prefix (e.g. ["app", "app/main.py"]) must render both nodes with
  // no duplicate-key React warning.
  it("handles a file and dir that share the same path prefix without duplicate keys", () => {
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    try {
      const files = [
        { path: "app", content: "# top-level file\n" },
        { path: "app/main.py", content: "# nested\n" },
      ];
      render(<CodeView files={files} />);
      // Both the "app" file node and the "app" directory node must appear.
      // The directory shows up as a collapsible row containing "main.py".
      // It may appear more than once (tree + tab), so we check at least one.
      expect(screen.getAllByText("main.py").length).toBeGreaterThan(0);
      // No duplicate-key console error from React.
      const keyWarnings = errorSpy.mock.calls.filter((args) =>
        String(args[0]).includes("same key"),
      );
      expect(keyWarnings).toHaveLength(0);
    } finally {
      errorSpy.mockRestore();
    }
  });
});
