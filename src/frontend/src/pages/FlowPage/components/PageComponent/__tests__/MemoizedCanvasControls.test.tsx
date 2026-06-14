import { render, screen } from "@testing-library/react";

const mockCurrentFlow = {
  id: "test-flow-id",
  name: "Test Flow",
  locked: false,
};

jest.mock("nanoid", () => ({
  nanoid: () => "test-id",
}));

jest.mock("../../flowSidebarComponent/components/sidebarSegmentedNav", () => ({
  NAV_ITEMS: [],
}));

jest.mock("@xyflow/react", () => ({
  Background: () => null,
  Panel: ({ children }) => <div>{children}</div>,
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: () => null,
  useSidebar: () => ({
    open: false,
    toggleSidebar: jest.fn(),
    setActiveSection: jest.fn(),
  }),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: false,
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector) => {
    const state = {
      currentFlow: mockCurrentFlow,
      setCurrentFlow: jest.fn(),
    };
    return selector(state);
  }),
}));

jest.mock("@/components/core/canvasControlsComponent/CanvasControls", () => ({
  __esModule: true,
  default: ({ children }) => (
    <div data-testid="canvas-controls">{children}</div>
  ),
}));

jest.mock(
  "@/components/core/canvasControlsComponent/CanvasControlButton",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

// eslint-disable-next-line import/first
import { MemoizedCanvasControls } from "../MemoizedComponents";

describe("MemoizedCanvasControls", () => {
  const defaultProps = {
    selectedNode: null,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentFlow.locked = false;
  });

  it("should_render_canvas_controls_wrapper", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.getByTestId("canvas-controls")).toBeInTheDocument();
  });

  it("should_not_render_lock_icon", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.queryByTestId("icon-Lock")).not.toBeInTheDocument();
    expect(screen.queryByTestId("icon-Unlock")).not.toBeInTheDocument();
  });

  it("should_not_render_lock_icon_when_flow_is_locked", () => {
    mockCurrentFlow.locked = true;

    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.queryByTestId("icon-Lock")).not.toBeInTheDocument();
  });

  it("should accept optional isAgentWorking prop without error", () => {
    expect(() =>
      render(
        <MemoizedCanvasControls {...defaultProps} isAgentWorking={true} />,
      ),
    ).not.toThrow();
    expect(screen.getByTestId("canvas-controls")).toBeInTheDocument();
  });

  it("should be memoized", () => {
    expect(MemoizedCanvasControls.$$typeof.toString()).toContain(
      "Symbol(react.memo)",
    );
  });
});
