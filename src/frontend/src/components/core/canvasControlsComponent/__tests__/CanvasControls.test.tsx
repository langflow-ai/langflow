import { fireEvent, render, screen } from "@testing-library/react";
import CanvasControls from "../CanvasControls";

const mockUndo = jest.fn();
const mockRedo = jest.fn();

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
    const state = {
      undo: mockUndo,
      redo: mockRedo,
    };
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

jest.mock("@/modals/flowLogsModal", () => ({
  __esModule: true,
  default: ({ children }) => (
    <div data-testid="flow-logs-modal">{children}</div>
  ),
}));

jest.mock("../CanvasControlsDropdown", () => ({
  __esModule: true,
  default: () => <div data-testid="controls-dropdown" />,
}));

jest.mock("@/assets/langflow_assistant.svg", () => "mock-assistant-icon.svg");

describe("CanvasControls", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_render_panel_with_all_controls_when_mounted", () => {
    render(<CanvasControls />);

    expect(screen.getByTestId("main_canvas_controls")).toBeInTheDocument();
    expect(screen.getByTestId("controls-dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("flow-logs-modal")).toBeInTheDocument();
  });

  it("should_render_assistant_button_with_new_badge", () => {
    render(<CanvasControls />);

    expect(screen.getByTitle("Langflow Assistant")).toBeInTheDocument();
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByAltText("Langflow Assistant")).toBeInTheDocument();
  });

  it("should_render_logs_button_with_terminal_icon", () => {
    render(<CanvasControls />);

    expect(screen.getByTitle("Logs")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Terminal")).toBeInTheDocument();
  });

  it("should_render_undo_button_with_icon", () => {
    render(<CanvasControls />);

    expect(screen.getByTitle("Undo")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Undo2")).toBeInTheDocument();
  });

  it("should_render_redo_button_with_icon", () => {
    render(<CanvasControls />);

    expect(screen.getByTitle("Redo")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Redo2")).toBeInTheDocument();
  });

  it("should_call_undo_when_undo_button_clicked", () => {
    render(<CanvasControls />);

    const undoButton = screen.getByTitle("Undo");
    fireEvent.click(undoButton);

    expect(mockUndo).toHaveBeenCalledTimes(1);
  });

  it("should_call_redo_when_redo_button_clicked", () => {
    render(<CanvasControls />);

    const redoButton = screen.getByTitle("Redo");
    fireEvent.click(redoButton);

    expect(mockRedo).toHaveBeenCalledTimes(1);
  });

  it("should_render_children_when_provided", () => {
    render(
      <CanvasControls>
        <div data-testid="child-element">Lock Button</div>
      </CanvasControls>,
    );

    expect(screen.getByTestId("child-element")).toBeInTheDocument();
  });

  it("should_position_panel_at_bottom_center", () => {
    render(<CanvasControls />);

    const panel = screen.getByTestId("main_canvas_controls");
    expect(panel).toHaveAttribute("position", "bottom-center");
  });

  it("should_have_bottom_padding_class_for_32px_spacing", () => {
    render(<CanvasControls />);

    const panel = screen.getByTestId("main_canvas_controls");
    expect(panel.className).toContain("!bottom-8");
  });
});
