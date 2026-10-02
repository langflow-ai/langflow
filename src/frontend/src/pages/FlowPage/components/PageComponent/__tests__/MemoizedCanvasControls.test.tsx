import { render, screen } from "@testing-library/react";

const mockCurrentFlow = {
  id: "test-flow-id",
  name: "Test Flow",
  locked: false,
};

const mockAssistantState = { isAssistantProcessing: false };

jest.mock("@/stores/assistantManagerStore", () => ({
  __esModule: true,
  default: (selector) => selector(mockAssistantState),
}));

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
  default: ({ children, effectiveLocked, assistantLocked }) => (
    <div
      data-testid="canvas-controls"
      data-effective-locked={String(Boolean(effectiveLocked))}
      data-assistant-locked={String(Boolean(assistantLocked))}
    >
      {children}
    </div>
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
    mockAssistantState.isAssistantProcessing = false;
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

  it("forwards the permission read-only state to canvas controls", () => {
    render(<MemoizedCanvasControls {...defaultProps} isReadOnly />);

    expect(screen.getByTestId("canvas-controls")).toHaveAttribute(
      "data-effective-locked",
      "true",
    );
  });

  it("should be memoized", () => {
    expect(MemoizedCanvasControls.$$typeof.toString()).toContain(
      "Symbol(react.memo)",
    );
  });

  it("keeps the assistant reachable when only its own run locks editing", () => {
    mockAssistantState.isAssistantProcessing = true;

    render(<MemoizedCanvasControls {...defaultProps} />);

    const controls = screen.getByTestId("canvas-controls");
    expect(controls).toHaveAttribute("data-effective-locked", "true");
    expect(controls).toHaveAttribute("data-assistant-locked", "false");
  });

  it.each([
    ["flow lock", true, false, false],
    ["permission restriction", false, true, false],
    ["external agent", false, false, true],
  ])(
    "preserves the %s during assistant processing",
    (_reason, locked, isReadOnly, isAgentWorking) => {
      mockCurrentFlow.locked = locked;
      mockAssistantState.isAssistantProcessing = true;

      render(
        <MemoizedCanvasControls
          {...defaultProps}
          isReadOnly={isReadOnly}
          isAgentWorking={isAgentWorking}
        />,
      );

      const controls = screen.getByTestId("canvas-controls");
      expect(controls).toHaveAttribute("data-effective-locked", "true");
      expect(controls).toHaveAttribute("data-assistant-locked", "true");
    },
  );
});
