import { act, fireEvent, render, screen } from "@testing-library/react";
import CanvasControls from "../CanvasControls";

// The modal/dialog/dropdown overlay layer in the app all sits at `z-50`
// (see ui/dialog.tsx, ui/popover.tsx). The assistant onboarding tooltip must
// stay at canvas level — strictly BELOW this layer — so it never floats in
// front of an open modal like "My Files".
const MODAL_LAYER_Z_INDEX = 50;
const ONBOARDING_TOOLTIP_DELAY_MS = 10_000;

// Extract the numeric z-index from a Tailwind className, supporting both the
// scale token (`z-40`) and the arbitrary-value form (`z-[60]`).
const getZIndex = (className: string): number | null => {
  const token = className
    .split(/\s+/)
    .find((cls) => /^z-(\[?\d+\]?)$/.test(cls));
  if (!token) return null;
  const digits = token.replace(/^z-\[?/, "").replace(/\]$/, "");
  return Number.parseInt(digits, 10);
};

const reactFlowFns = {
  fitView: jest.fn(),
  zoomIn: jest.fn(),
  zoomOut: jest.fn(),
  zoomTo: jest.fn(),
};

jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...props }) => (
    <div data-testid="panel" {...props}>
      {children}
    </div>
  ),
  useReactFlow: () => reactFlowFns,
  useStore: () => ({
    isInteractive: true,
    minZoomReached: false,
    maxZoomReached: false,
    zoom: 1,
  }),
  useStoreApi: () => ({ setState: jest.fn() }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn(() => false),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector) => {
    const state = {};
    return selector(state);
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, title, ...rest }) => (
    <button onClick={onClick} title={title} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("../CanvasControlsDropdown", () => ({
  __esModule: true,
  default: () => <div data-testid="controls-dropdown" />,
}));

jest.mock("../HelpDropdown", () => ({
  __esModule: true,
  default: () => <div data-testid="help-dropdown" />,
}));

jest.mock("@/assets/langflow_assistant.svg", () => "mock-assistant-icon.svg");
jest.mock(
  "@/assets/langflow_assistant_idle.svg",
  () => "mock-assistant-idle-icon.svg",
);

jest.mock("@/stores/assistantManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector) => {
    const state = { toggleAssistant: jest.fn() };
    return typeof selector === "function" ? selector(state) : state;
  }),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_INSPECTION_PANEL: false,
}));

jest.mock("zustand/react/shallow", () => ({
  useShallow: (fn: unknown) => fn,
}));

describe("CanvasControls", () => {
  const mockDispatchEvent = jest.fn();
  const originalDispatchEvent = window.dispatchEvent;

  beforeEach(() => {
    jest.clearAllMocks();
    window.dispatchEvent = mockDispatchEvent;
  });

  afterEach(() => {
    window.dispatchEvent = originalDispatchEvent;
  });

  it("should_render_panel_with_all_controls_when_mounted", () => {
    render(<CanvasControls selectedNode={null} />);

    expect(screen.getByTestId("main_canvas_controls")).toBeInTheDocument();
    expect(screen.getByTestId("controls-dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("help-dropdown")).toBeInTheDocument();
  });

  it("should_render_assistant_button_with_new_badge", () => {
    render(<CanvasControls selectedNode={null} />);

    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByAltText("Langflow Assistant")).toBeInTheDocument();
  });

  it("should_render_sticky_note_button", () => {
    render(<CanvasControls selectedNode={null} />);

    expect(screen.getByTitle("Add Sticky Note")).toBeInTheDocument();
    expect(screen.getByTestId("icon-sticky-note")).toBeInTheDocument();
  });

  it("should_dispatch_add_note_event_when_sticky_note_clicked", () => {
    render(<CanvasControls selectedNode={null} />);

    const stickyNoteButton = screen.getByTitle("Add Sticky Note");
    fireEvent.click(stickyNoteButton);

    expect(mockDispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: "lf:start-add-note" }),
    );
  });

  it("should_render_children_when_provided", () => {
    render(
      <CanvasControls selectedNode={null}>
        <div data-testid="child-element">Lock Button</div>
      </CanvasControls>,
    );

    expect(screen.getByTestId("child-element")).toBeInTheDocument();
  });

  it("should_position_panel_at_bottom_center", () => {
    render(<CanvasControls selectedNode={null} />);

    const panel = screen.getByTestId("main_canvas_controls");
    expect(panel).toHaveAttribute("position", "bottom-center");
  });

  it("should_have_overflow_visible_class_on_panel", () => {
    render(<CanvasControls selectedNode={null} />);

    const panel = screen.getByTestId("main_canvas_controls");
    expect(panel.className).toContain("!overflow-visible");
  });

  it("should_render_onboarding_tooltip_below_modal_layer_when_active", () => {
    // Arrange — fresh browser (assistant not yet discovered) so the onboarding
    // tooltip is eligible to surface after the idle delay.
    localStorage.clear();
    jest.useFakeTimers();

    try {
      render(<CanvasControls selectedNode={null} />);

      // Act — let the idle delay elapse so the popover opens and the tooltip
      // (rendered via a Portal on document.body) mounts.
      act(() => {
        jest.advanceTimersByTime(ONBOARDING_TOOLTIP_DELAY_MS);
      });

      // Assert — the tooltip stays at canvas level: its z-index must be below
      // the z-50 modal/dialog layer so it never floats over an open modal.
      const tooltip = screen.getByTestId("assistant-onboarding-tooltip");
      const zIndex = getZIndex(tooltip.className);

      expect(zIndex).not.toBeNull();
      expect(zIndex as number).toBeLessThan(MODAL_LAYER_Z_INDEX);
    } finally {
      jest.useRealTimers();
    }
  });
});
