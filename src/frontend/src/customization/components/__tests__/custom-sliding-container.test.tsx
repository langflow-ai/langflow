import { fireEvent, render, screen } from "@testing-library/react";
import { SlidingContainer } from "../custom-sliding-container";

describe("SlidingContainer", () => {
  const defaultProps = {
    isOpen: false,
    children: <div>Test Content</div>,
  };

  beforeEach(() => {
    // Mock window.innerWidth
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1200,
    });
  });

  it("should render children when open", () => {
    render(<SlidingContainer {...defaultProps} isOpen={true} />);

    expect(screen.getByText("Test Content")).toBeInTheDocument();
  });

  it("should set width to 0px when closed", () => {
    const { container } = render(
      <SlidingContainer {...defaultProps} isOpen={false} />,
    );

    const slidingContainer = container.firstChild as HTMLElement;
    expect(slidingContainer).toHaveStyle({ width: "0px" });
  });

  it("should use default width when open", () => {
    render(<SlidingContainer {...defaultProps} isOpen={true} />);

    const container = screen.getByText("Test Content").parentElement
      ?.parentElement as HTMLElement;
    expect(container).toHaveStyle({ width: "400px" });
  });

  it("should set width to 100% when fullscreen", () => {
    render(
      <SlidingContainer {...defaultProps} isOpen={true} isFullscreen={true} />,
    );

    const container = screen.getByText("Test Content").parentElement
      ?.parentElement as HTMLElement;
    expect(container).toHaveStyle({ width: "100%" });
  });

  it("should show resize handle only when resizable, open, and not fullscreen", () => {
    const { rerender } = render(
      <SlidingContainer {...defaultProps} isOpen={true} resizable={true} />,
    );
    expect(screen.getByLabelText("Resize panel")).toBeInTheDocument();

    rerender(
      <SlidingContainer {...defaultProps} isOpen={false} resizable={true} />,
    );
    expect(screen.queryByLabelText("Resize panel")).not.toBeInTheDocument();

    rerender(
      <SlidingContainer {...defaultProps} isOpen={true} resizable={false} />,
    );
    expect(screen.queryByLabelText("Resize panel")).not.toBeInTheDocument();

    rerender(
      <SlidingContainer
        {...defaultProps}
        isOpen={true}
        resizable={true}
        isFullscreen={true}
      />,
    );
    expect(screen.queryByLabelText("Resize panel")).not.toBeInTheDocument();
  });

  it("should call onWidthChange when resizing", () => {
    const onWidthChange = jest.fn();
    render(
      <SlidingContainer
        {...defaultProps}
        isOpen={true}
        resizable={true}
        onWidthChange={onWidthChange}
      />,
    );

    const resizeHandle = screen.getByLabelText("Resize panel");

    // Simulate mouse down on resize handle
    fireEvent.mouseDown(resizeHandle, {
      clientX: 800,
      preventDefault: jest.fn(),
    });

    // Simulate mouse move on document (the component listens to document events)
    const mouseMoveEvent = new MouseEvent("mousemove", {
      bubbles: true,
      cancelable: true,
      clientX: 700,
    });
    document.dispatchEvent(mouseMoveEvent);

    // onWidthChange should be called with new width (window.innerWidth - clientX)
    expect(onWidthChange).toHaveBeenCalledWith(500); // 1200 - 700 = 500
  });
});
