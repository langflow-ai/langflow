import { fireEvent, render, screen } from "@testing-library/react";
import { MemoizedCanvasControls } from "../MemoizedComponents";

const mockSetIsLassoMode = jest.fn();
let mockStoreState = {
  currentFlow: { locked: false } as { locked: boolean } | null,
  isLassoMode: false,
  setIsLassoMode: mockSetIsLassoMode,
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector: (s: typeof mockStoreState) => unknown) =>
    selector(mockStoreState),
  ),
}));

jest.mock("zustand/react/shallow", () => ({
  useShallow: (fn: (s: typeof mockStoreState) => unknown) => fn,
}));

jest.mock("@/components/core/logCanvasControlsComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../../flowSidebarComponent", () => ({
  useSearchContext: () => ({ focusSearch: jest.fn(), isSearchFocused: false }),
}));

jest.mock("../../flowSidebarComponent/components/sidebarSegmentedNav", () => ({
  NAV_ITEMS: [],
}));

jest.mock("@/components/core/canvasControlsComponent/CanvasControls", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="canvas-controls">{children}</div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    title,
    unstyled: _unstyled,
    unselectable: _unselectable,
    ...rest
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    children?: React.ReactNode;
    unstyled?: boolean;
    unselectable?: string;
  }) => (
    <button onClick={onClick} disabled={disabled} title={title} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: ({ orientation }: { orientation: string }) => (
    <div data-testid={`separator-${orientation}`} />
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: (string | boolean | undefined)[]) =>
    classes.filter(Boolean).join(" "),
}));

const defaultProps = {
  setIsAddingNote: jest.fn(),
  shadowBoxWidth: 200,
  shadowBoxHeight: 100,
  selectedNode: null,
};

describe("MemoizedCanvasControls", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStoreState = {
      currentFlow: { locked: false },
      isLassoMode: false,
      setIsLassoMode: mockSetIsLassoMode,
    };
  });

  describe("lasso toggle button rendering", () => {
    it("renders the lasso toggle button", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("lasso-mode-toggle")).toBeInTheDocument();
    });

    it("renders the LassoSelect icon", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("icon-LassoSelect")).toBeInTheDocument();
    });

    it("shows 'Lasso Select' title when inactive", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("lasso-mode-toggle")).toHaveAttribute(
        "title",
        "Lasso Select",
      );
    });

    it("shows 'Exit Lasso Select (Esc)' title when active", () => {
      mockStoreState.isLassoMode = true;
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("lasso-mode-toggle")).toHaveAttribute(
        "title",
        "Exit Lasso Select (Esc)",
      );
    });
  });

  describe("lasso mode active state styling", () => {
    it("does not apply bg-accent class when isLassoMode is false", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      const button = screen.getByTestId("lasso-mode-toggle");
      expect(button.className).not.toContain("bg-accent");
    });

    it("applies bg-accent class when isLassoMode is true", () => {
      mockStoreState.isLassoMode = true;
      render(<MemoizedCanvasControls {...defaultProps} />);
      const button = screen.getByTestId("lasso-mode-toggle");
      expect(button.className).toContain("bg-accent");
    });

    it("icon uses muted color when inactive", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      const icon = screen.getByTestId("icon-LassoSelect");
      expect(icon.className).toContain("text-muted-foreground");
    });

    it("icon uses primary color when active", () => {
      mockStoreState.isLassoMode = true;
      render(<MemoizedCanvasControls {...defaultProps} />);
      const icon = screen.getByTestId("icon-LassoSelect");
      expect(icon.className).toContain("text-primary");
    });
  });

  describe("lasso toggle click handler", () => {
    it("calls setIsLassoMode(true) when clicked while inactive", () => {
      mockStoreState.isLassoMode = false;
      render(<MemoizedCanvasControls {...defaultProps} />);

      fireEvent.click(screen.getByTestId("lasso-mode-toggle"));

      expect(mockSetIsLassoMode).toHaveBeenCalledTimes(1);
      expect(mockSetIsLassoMode).toHaveBeenCalledWith(true);
    });

    it("calls setIsLassoMode(false) when clicked while active", () => {
      mockStoreState.isLassoMode = true;
      render(<MemoizedCanvasControls {...defaultProps} />);

      fireEvent.click(screen.getByTestId("lasso-mode-toggle"));

      expect(mockSetIsLassoMode).toHaveBeenCalledTimes(1);
      expect(mockSetIsLassoMode).toHaveBeenCalledWith(false);
    });
  });

  describe("disabled when flow is locked", () => {
    it("disables the lasso button when currentFlow.locked is true", () => {
      mockStoreState.currentFlow = { locked: true };
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("lasso-mode-toggle")).toBeDisabled();
    });

    it("does not disable the lasso button when currentFlow.locked is false", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("lasso-mode-toggle")).not.toBeDisabled();
    });
  });

  describe("separator between lasso button and lock status", () => {
    it("renders a vertical separator between the two buttons", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("separator-vertical")).toBeInTheDocument();
    });
  });

  describe("lock status icon", () => {
    it("shows Unlock icon when flow is not locked", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("icon-Unlock")).toBeInTheDocument();
      expect(screen.queryByTestId("icon-Lock")).not.toBeInTheDocument();
    });

    it("shows Lock icon when flow is locked", () => {
      mockStoreState.currentFlow = { locked: true };
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("icon-Lock")).toBeInTheDocument();
      expect(screen.queryByTestId("icon-Unlock")).not.toBeInTheDocument();
    });

    it("shows 'Flow Locked' text when flow is locked", () => {
      mockStoreState.currentFlow = { locked: true };
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByText("Flow Locked")).toBeInTheDocument();
    });

    it("does not show 'Flow Locked' text when flow is unlocked", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.queryByText("Flow Locked")).not.toBeInTheDocument();
    });
  });

  describe("component structure", () => {
    it("wraps content in CanvasControls", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(screen.getByTestId("canvas-controls")).toBeInTheDocument();
    });

    it("is a memoized component", () => {
      expect(MemoizedCanvasControls.$$typeof.toString()).toContain(
        "Symbol(react.memo)",
      );
    });
  });
});
