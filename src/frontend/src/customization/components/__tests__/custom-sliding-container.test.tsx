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

  describe("rendering", () => {
    it("should render children when open", () => {
      render(<SlidingContainer {...defaultProps} isOpen={true} />);

      expect(screen.getByText("Test Content")).toBeInTheDocument();
    });

    it("should not render children when closed", () => {
      const { container } = render(
        <SlidingContainer {...defaultProps} isOpen={false} />,
      );

      // Content should still be in DOM but container should have 0 width
      const slidingContainer = container.firstChild as HTMLElement;
      expect(slidingContainer).toHaveStyle({ width: "0px" });
    });

    it("should apply custom className", () => {
      const { container } = render(
        <SlidingContainer
          {...defaultProps}
          isOpen={true}
          className="custom-class"
        />,
      );

      const slidingContainer = container.firstChild as HTMLElement;
      expect(slidingContainer).toHaveClass("custom-class");
    });
  });

  describe("width behavior", () => {
    it("should use default width when not specified", () => {
      render(<SlidingContainer {...defaultProps} isOpen={true} />);

      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;
      expect(container).toHaveStyle({ width: "400px" });
    });

    it("should use custom width when specified", () => {
      render(<SlidingContainer {...defaultProps} isOpen={true} width={600} />);

      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;
      expect(container).toHaveStyle({ width: "600px" });
    });

    it("should set width to 0px when closed", () => {
      render(<SlidingContainer {...defaultProps} isOpen={false} width={600} />);

      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;
      expect(container).toHaveStyle({ width: "0px" });
    });

    it("should set width to 100% when fullscreen", () => {
      render(
        <SlidingContainer
          {...defaultProps}
          isOpen={true}
          isFullscreen={true}
        />,
      );

      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;
      expect(container).toHaveStyle({ width: "100%" });
    });
  });

  describe("resizable behavior", () => {
    it("should not show resize handle when resizable is false", () => {
      render(
        <SlidingContainer {...defaultProps} isOpen={true} resizable={false} />,
      );

      expect(screen.queryByLabelText("Resize panel")).not.toBeInTheDocument();
    });

    it("should not show resize handle when closed", () => {
      render(
        <SlidingContainer {...defaultProps} isOpen={false} resizable={true} />,
      );

      expect(screen.queryByLabelText("Resize panel")).not.toBeInTheDocument();
    });

    it("should not show resize handle when fullscreen", () => {
      render(
        <SlidingContainer
          {...defaultProps}
          isOpen={true}
          resizable={true}
          isFullscreen={true}
        />,
      );

      expect(screen.queryByLabelText("Resize panel")).not.toBeInTheDocument();
    });

    it("should show resize handle when resizable, open, and not fullscreen", () => {
      render(
        <SlidingContainer {...defaultProps} isOpen={true} resizable={true} />,
      );

      expect(screen.getByLabelText("Resize panel")).toBeInTheDocument();
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

    it("should not call onWidthChange when resizable is false", () => {
      const onWidthChange = jest.fn();
      render(
        <SlidingContainer
          {...defaultProps}
          isOpen={true}
          resizable={false}
          onWidthChange={onWidthChange}
        />,
      );

      // Try to trigger resize (should not work)
      fireEvent.mouseDown(document.body, { clientX: 800 });
      fireEvent.mouseMove(window, { clientX: 700 });

      expect(onWidthChange).not.toHaveBeenCalled();
    });

    it("should stop resizing on mouse up", () => {
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

      // Start resizing
      fireEvent.mouseDown(resizeHandle, { clientX: 800 });
      fireEvent.mouseMove(window, { clientX: 700 });

      const callCountBefore = onWidthChange.mock.calls.length;

      // Stop resizing
      fireEvent.mouseUp(window);

      // Move mouse again (should not trigger onWidthChange)
      fireEvent.mouseMove(window, { clientX: 600 });

      // onWidthChange should not have been called again
      expect(onWidthChange.mock.calls.length).toBe(callCountBefore);
    });
  });

  describe("transition duration", () => {
    it("should use default duration when not specified", () => {
      render(<SlidingContainer {...defaultProps} isOpen={true} />);

      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;
      expect(container).toHaveStyle({ transitionDuration: "300ms" });
    });

    it("should use custom duration when specified", () => {
      render(
        <SlidingContainer {...defaultProps} isOpen={true} duration={500} />,
      );

      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;
      expect(container).toHaveStyle({ transitionDuration: "500ms" });
    });

    it("should disable transition during resize", () => {
      render(
        <SlidingContainer
          {...defaultProps}
          isOpen={true}
          resizable={true}
          duration={500}
        />,
      );

      const resizeHandle = screen.getByLabelText("Resize panel");
      const container = screen.getByText("Test Content").parentElement
        ?.parentElement as HTMLElement;

      // Start resizing
      fireEvent.mouseDown(resizeHandle);

      // Transition should be disabled during resize
      expect(container).toHaveStyle({ transitionDuration: "0ms" });
    });
  });
});
