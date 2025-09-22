import { fireEvent, render, screen } from "@testing-library/react";
import CanvasControlsDropdown, {
  KEYBOARD_SHORTCUTS,
} from "../CanvasControlsDropdown";

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children, open, onOpenChange }) => (
    <div data-testid="dropdown-menu" data-open={open}>
      <button
        onClick={() => onOpenChange?.(!open)}
        aria-expanded={open}
        aria-haspopup="true"
        type="button"
      >
        {children}
      </button>
    </div>
  ),
  DropdownMenuContent: ({ children }) => (
    <div data-testid="dropdown-content">{children}</div>
  ),
  DropdownMenuTrigger: ({ children }) => (
    <div data-testid="dropdown-trigger">{children}</div>
  ),
}));
jest.mock("@/components/ui/separator", () => ({
  Separator: () => <div data-testid="separator" />,
}));
jest.mock("../DropdownControlButton", () => ({
  __esModule: true,
  default: ({ label, onClick, disabled, testId, shortcut }) => (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
    >
      {label} ({shortcut})
    </button>
  ),
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }) => <span data-testid="icon">{name}</span>,
}));

// Minimize utils import surface (prevents pulling stores/darkStore via utils.ts)
jest.mock("@/utils/utils", () => ({
  __esModule: true,
  getOS: () => "macos",
  cn: (...args) => args.filter(Boolean).join(" "),
}));

const fitView = jest.fn();
const zoomIn = jest.fn();
const zoomOut = jest.fn();
const zoomTo = jest.fn();

jest.mock("@xyflow/react", () => ({
  useReactFlow: () => ({ fitView, zoomIn, zoomOut, zoomTo }),
  useStore: (selector) =>
    selector({
      nodesDraggable: true,
      nodesConnectable: true,
      elementsSelectable: true,
      transform: [0, 0, 1],
      minZoom: 0.2,
      maxZoom: 2,
    }),
}));

describe("CanvasControlsDropdown", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders current zoom percentage and toggles menu", () => {
    render(<CanvasControlsDropdown />);
    expect(screen.getByText("100%"));
    fireEvent.click(screen.getByTestId("canvas_controls_dropdown"));
    expect(screen.getByTestId("dropdown-content")).toBeInTheDocument();
  });

  it("handles zoom in/out, fit and reset via click", () => {
    render(<CanvasControlsDropdown />);
    fireEvent.click(screen.getByTestId("canvas_controls_dropdown"));

    fireEvent.click(screen.getByTestId("zoom_in"));
    expect(zoomIn).toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("zoom_out"));
    expect(zoomOut).toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("fit_view"));
    expect(fitView).toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("reset_zoom"));
    expect(zoomTo).toHaveBeenCalledWith(1);
  });

  it("handles keyboard shortcuts with modifier", () => {
    render(<CanvasControlsDropdown />);

    const keydown = (code: string) =>
      document.dispatchEvent(
        new KeyboardEvent("keydown", { code, metaKey: true }),
      );

    keydown(KEYBOARD_SHORTCUTS.ZOOM_IN.code);
    expect(zoomIn).toHaveBeenCalled();

    keydown(KEYBOARD_SHORTCUTS.ZOOM_OUT.code);
    expect(zoomOut).toHaveBeenCalled();

    keydown(KEYBOARD_SHORTCUTS.FIT_VIEW.code);
    expect(fitView).toHaveBeenCalled();

    keydown(KEYBOARD_SHORTCUTS.RESET_ZOOM.code);
    expect(zoomTo).toHaveBeenCalledWith(1);
  });

  it("does not zoom out when at minimum zoom", () => {
    // Temporarily override the useStore mock for this test
    const originalUseStore = jest.requireMock("@xyflow/react").useStore;
    jest.requireMock("@xyflow/react").useStore = jest.fn((selector) =>
      selector({
        nodesDraggable: true,
        nodesConnectable: true,
        elementsSelectable: true,
        transform: [0, 0, 0.25], // At minimum zoom
        minZoom: 0.25,
        maxZoom: 2,
      }),
    );

    render(<CanvasControlsDropdown />);

    const keydown = (code: string) =>
      document.dispatchEvent(
        new KeyboardEvent("keydown", { code, metaKey: true }),
      );

    keydown(KEYBOARD_SHORTCUTS.ZOOM_OUT.code);
    expect(zoomOut).not.toHaveBeenCalled();

    // Restore original mock
    jest.requireMock("@xyflow/react").useStore = originalUseStore;
  });

  it("does not zoom in when at maximum zoom", () => {
    // Temporarily override the useStore mock for this test
    const originalUseStore = jest.requireMock("@xyflow/react").useStore;
    jest.requireMock("@xyflow/react").useStore = jest.fn((selector) =>
      selector({
        nodesDraggable: true,
        nodesConnectable: true,
        elementsSelectable: true,
        transform: [0, 0, 2], // At maximum zoom
        minZoom: 0.25,
        maxZoom: 2,
      }),
    );

    render(<CanvasControlsDropdown />);

    const keydown = (code: string) =>
      document.dispatchEvent(
        new KeyboardEvent("keydown", { code, metaKey: true }),
      );

    keydown(KEYBOARD_SHORTCUTS.ZOOM_IN.code);
    expect(zoomIn).not.toHaveBeenCalled();

    // Restore original mock
    jest.requireMock("@xyflow/react").useStore = originalUseStore;
  });
});
