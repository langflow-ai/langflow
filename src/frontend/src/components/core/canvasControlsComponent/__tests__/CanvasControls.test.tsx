import { fireEvent, render, screen } from "@testing-library/react";
import CanvasControls from "../CanvasControls";

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
});
