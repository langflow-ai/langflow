import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import CanvasControls from "../CanvasControls";

jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...props }) => (
    <div data-testid="panel" {...props}>
      {children}
    </div>
  ),
  useReactFlow: () => ({
    fitView: jest.fn(),
    zoomIn: jest.fn(),
    zoomOut: jest.fn(),
    zoomTo: jest.fn(),
  }),
  useUpdateNodeInternals: () => jest.fn(),
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
  default: jest.fn((selector) => {
    const state = {
      nodes: [],
      edges: [],
      setNodes: jest.fn(),
      currentFlow: { locked: false },
    };
    return typeof selector === "function" ? selector(state) : false;
  }),
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
    <span data-testid={`icon-${name}`} className={className} aria-hidden="true">
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

describe("CanvasControls toolbar accessibility", () => {
  it("should_have_no_axe_violations_when_unlocked", async () => {
    const { container } = render(<CanvasControls selectedNode={null} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_when_locked", async () => {
    const { container } = render(
      <CanvasControls selectedNode={null} effectiveLocked />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_accessible_name_for_add_note_button", () => {
    render(<CanvasControls selectedNode={null} />);

    expect(
      screen.getByRole("button", { name: "Add Sticky Note" }),
    ).toBeInTheDocument();
  });

  it("should_expose_accessible_name_for_minimize_all_button", () => {
    render(<CanvasControls selectedNode={null} />);

    expect(
      screen.getByRole("button", { name: "Minimize all" }),
    ).toBeInTheDocument();
  });

  it("should_expose_read_only_accessible_name_when_locked", () => {
    render(<CanvasControls selectedNode={null} effectiveLocked />);

    expect(screen.getByTestId("canvas-add-note-button")).toHaveAccessibleName(
      "(Read-Only)",
    );
    expect(
      screen.getByTestId("canvas_controls_minimize_all"),
    ).toHaveAccessibleName("(Read-Only)");
  });
});
