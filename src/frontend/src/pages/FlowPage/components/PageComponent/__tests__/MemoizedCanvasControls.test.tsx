import { fireEvent, render, screen } from "@testing-library/react";

const mockSaveFlow = jest.fn(() => Promise.resolve());
const mockSetCurrentFlow = jest.fn();

const mockCurrentFlow = {
  id: "test-flow-id",
  name: "Test Flow",
  locked: false,
};

jest.mock("nanoid", () => ({
  nanoid: () => "test-id",
}));

jest.mock("../../flowSidebarComponent", () => ({
  useSearchContext: () => ({
    focusSearch: jest.fn(),
    isSearchFocused: false,
  }),
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
      setCurrentFlow: mockSetCurrentFlow,
    };
    return selector(state);
  }),
}));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
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

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, title, className, ...rest }) => (
    <button onClick={onClick} title={title} className={className} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

// eslint-disable-next-line import/first
import { MemoizedCanvasControls } from "../MemoizedComponents";

describe("MemoizedCanvasControls", () => {
  const defaultProps = {
    setIsAddingNote: jest.fn(),
    shadowBoxWidth: 100,
    shadowBoxHeight: 100,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentFlow.locked = false;
  });

  it("should_render_unlock_icon_when_flow_is_not_locked", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.getByTestId("icon-Unlock")).toBeInTheDocument();
    expect(screen.queryByTestId("icon-Lock")).not.toBeInTheDocument();
  });

  it("should_render_lock_icon_when_flow_is_locked", () => {
    mockCurrentFlow.locked = true;

    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.getByTestId("icon-Lock")).toBeInTheDocument();
    expect(screen.queryByTestId("icon-Unlock")).not.toBeInTheDocument();
  });

  it("should_show_unlock_flow_title_when_flow_is_locked", () => {
    mockCurrentFlow.locked = true;

    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.getByTitle("Unlock flow")).toBeInTheDocument();
  });

  it("should_show_lock_flow_title_when_flow_is_not_locked", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.getByTitle("Lock flow")).toBeInTheDocument();
  });

  it("should_call_save_flow_and_set_current_flow_when_lock_button_clicked", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    const lockButton = screen.getByTestId("lock-status");
    fireEvent.click(lockButton);

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    expect(mockSetCurrentFlow).toHaveBeenCalledTimes(1);

    const savedFlow = mockSaveFlow.mock.calls[0][0];
    expect(savedFlow.locked).toBe(true);
  });

  it("should_toggle_lock_state_from_locked_to_unlocked", () => {
    mockCurrentFlow.locked = true;

    render(<MemoizedCanvasControls {...defaultProps} />);

    const lockButton = screen.getByTestId("lock-status");
    fireEvent.click(lockButton);

    const savedFlow = mockSaveFlow.mock.calls[0][0];
    expect(savedFlow.locked).toBe(false);
  });

  it("should_apply_destructive_color_class_when_flow_is_locked", () => {
    mockCurrentFlow.locked = true;

    render(<MemoizedCanvasControls {...defaultProps} />);

    const icon = screen.getByTestId("icon-Lock");
    expect(icon.className).toContain("text-destructive");
  });

  it("should_not_apply_destructive_color_class_when_flow_is_unlocked", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    const icon = screen.getByTestId("icon-Unlock");
    expect(icon.className).not.toContain("text-destructive");
  });

  it("should_render_inside_canvas_controls_wrapper", () => {
    render(<MemoizedCanvasControls {...defaultProps} />);

    expect(screen.getByTestId("canvas-controls")).toBeInTheDocument();
    expect(screen.getByTestId("lock-status")).toBeInTheDocument();
  });
});
