import { act, render, screen, waitFor } from "@testing-library/react";
import DurationDisplay from "../DurationDisplay";

// Mock AnimatedNumber component
jest.mock("../../../common/animatedNumbers", () => ({
  AnimatedNumber: ({ value, humanizedValue }: any) => (
    <span data-testid="animated-number" data-value={value}>
      {humanizedValue}
    </span>
  ),
}));

// Mock Loading component
jest.mock("../../../ui/loading", () => ({
  __esModule: true,
  default: ({ className }: any) => (
    <div data-testid="loading-spinner" className={className}>
      Loading...
    </div>
  ),
}));

describe("DurationDisplay", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("should render with finished duration", () => {
    render(<DurationDisplay duration={1500} chatId="test-chat-1" />);

    const animatedNumber = screen.getByTestId("animated-number");
    expect(animatedNumber).toBeInTheDocument();
    expect(animatedNumber.textContent).toBe("1.5s");
  });

  it("should show loading spinner when duration is undefined", () => {
    render(<DurationDisplay duration={undefined} chatId="test-chat-2" />);

    const loadingSpinner = screen.getByTestId("loading-spinner");
    expect(loadingSpinner).toBeInTheDocument();
  });

  it("should display '< 0.1s' for very small durations", () => {
    render(<DurationDisplay duration={30} chatId="test-chat-3" />);

    const animatedNumber = screen.getByTestId("animated-number");
    expect(animatedNumber.textContent).toBe("< 0.1s");
  });

  it("should start counting from 0 when duration is undefined", () => {
    render(<DurationDisplay duration={undefined} chatId="test-chat-4" />);

    const animatedNumber = screen.getByTestId("animated-number");
    expect(animatedNumber).toHaveAttribute("data-value", "0");
  });

  it("should increment timer based on Date.now() when loading", async () => {
    const realDateNow = Date.now;
    let mockTime = 1000000;

    Date.now = jest.fn(() => mockTime);

    render(<DurationDisplay duration={undefined} chatId="test-chat-5" />);

    // Initial state should be 0
    let animatedNumber = screen.getByTestId("animated-number");
    expect(parseFloat(animatedNumber.getAttribute("data-value") || "0")).toBe(
      0,
    );

    // Advance time by 500ms
    mockTime += 500;
    act(() => {
      jest.advanceTimersByTime(100);
    });

    await waitFor(() => {
      animatedNumber = screen.getByTestId("animated-number");
      const value = parseFloat(
        animatedNumber.getAttribute("data-value") || "0",
      );
      expect(value).toBeGreaterThanOrEqual(0.5);
    });

    // Advance time by another 500ms (total 1000ms)
    mockTime += 500;
    act(() => {
      jest.advanceTimersByTime(100);
    });

    await waitFor(() => {
      animatedNumber = screen.getByTestId("animated-number");
      const value = parseFloat(
        animatedNumber.getAttribute("data-value") || "0",
      );
      expect(value).toBeGreaterThanOrEqual(1);
    });

    Date.now = realDateNow;
  });

  it("should continue counting even when tab is inactive (simulated)", async () => {
    const realDateNow = Date.now;
    let mockTime = 1000000;

    Date.now = jest.fn(() => mockTime);

    render(<DurationDisplay duration={undefined} chatId="test-chat-6" />);

    // Simulate 2 seconds passing (like tab was inactive)
    mockTime += 2000;

    // Trigger the interval callback
    act(() => {
      jest.advanceTimersByTime(100);
    });

    await waitFor(() => {
      const animatedNumber = screen.getByTestId("animated-number");
      const value = parseFloat(
        animatedNumber.getAttribute("data-value") || "0",
      );
      // Should reflect the full 2 seconds, not just interval ticks
      expect(value).toBeGreaterThanOrEqual(2);
    });

    Date.now = realDateNow;
  });

  it("should stop counting when duration becomes defined", async () => {
    const realDateNow = Date.now;
    let mockTime = 1000000;

    Date.now = jest.fn(() => mockTime);

    const { rerender } = render(
      <DurationDisplay duration={undefined} chatId="test-chat-7" />,
    );

    // Advance time
    mockTime += 1000;
    act(() => {
      jest.advanceTimersByTime(100);
    });

    await waitFor(() => {
      const animatedNumber = screen.getByTestId("animated-number");
      const value = parseFloat(
        animatedNumber.getAttribute("data-value") || "0",
      );
      expect(value).toBeGreaterThanOrEqual(1);
    });

    // Now provide a final duration
    rerender(<DurationDisplay duration={1234} chatId="test-chat-7" />);

    const animatedNumber = screen.getByTestId("animated-number");
    expect(animatedNumber.textContent).toBe("1.2s");

    // Advance time more - value should not change
    mockTime += 5000;
    act(() => {
      jest.advanceTimersByTime(100);
    });

    expect(animatedNumber.textContent).toBe("1.2s");

    Date.now = realDateNow;
  });

  it("should reset timer when switching between different chats", async () => {
    const realDateNow = Date.now;
    let mockTime = 1000000;

    Date.now = jest.fn(() => mockTime);

    const { rerender } = render(
      <DurationDisplay duration={undefined} chatId="chat-1" />,
    );

    mockTime += 1000;
    act(() => {
      jest.advanceTimersByTime(100);
    });

    await waitFor(() => {
      const animatedNumber = screen.getByTestId("animated-number");
      const value = parseFloat(
        animatedNumber.getAttribute("data-value") || "0",
      );
      expect(value).toBeGreaterThanOrEqual(1);
    });

    // Switch to different chat
    rerender(<DurationDisplay duration={undefined} chatId="chat-2" />);

    // Timer should reset for new chat
    const animatedNumber = screen.getByTestId("animated-number");
    const value = parseFloat(animatedNumber.getAttribute("data-value") || "0");
    expect(value).toBeLessThan(1);

    Date.now = realDateNow;
  });

  it("should use 100ms interval for updates", () => {
    const setIntervalSpy = jest.spyOn(global, "setInterval");

    render(<DurationDisplay duration={undefined} chatId="test-chat-8" />);

    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 100);

    setIntervalSpy.mockRestore();
  });

  it("should cleanup interval on unmount", () => {
    const clearIntervalSpy = jest.spyOn(global, "clearInterval");

    const { unmount } = render(
      <DurationDisplay duration={undefined} chatId="test-chat-9" />,
    );

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();

    clearIntervalSpy.mockRestore();
  });

  it("should format durations correctly", () => {
    const testCases = [
      { duration: 0, expected: "< 0.1s" },
      { duration: 40, expected: "< 0.1s" },
      { duration: 100, expected: "0.1s" },
      { duration: 500, expected: "0.5s" },
      { duration: 1000, expected: "1.0s" },
      { duration: 1234, expected: "1.2s" },
      { duration: 5678, expected: "5.7s" },
      { duration: 10000, expected: "10.0s" },
    ];

    testCases.forEach(({ duration, expected }) => {
      const { unmount } = render(
        <DurationDisplay duration={duration} chatId={`test-${duration}`} />,
      );

      const animatedNumber = screen.getByTestId("animated-number");
      expect(animatedNumber.textContent).toBe(expected);

      unmount();
    });
  });

  describe("playground remount behavior", () => {
    it("should not reset timer when component remounts with same chatId", async () => {
      const realDateNow = Date.now;
      let mockTime = 1000000;
      Date.now = jest.fn(() => mockTime);

      // First mount
      const { unmount } = render(
        <DurationDisplay duration={undefined} chatId="playground-chat-1" />,
      );

      // Advance time by 1 second
      mockTime += 1000;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      await waitFor(() => {
        const animatedNumber = screen.getByTestId("animated-number");
        const value = parseFloat(
          animatedNumber.getAttribute("data-value") || "0",
        );
        expect(value).toBeGreaterThanOrEqual(1);
      });

      // Unmount component (simulate closing playground)
      unmount();

      // Advance time by another second while unmounted
      mockTime += 1000;

      // Remount component (simulate reopening playground)
      render(
        <DurationDisplay duration={undefined} chatId="playground-chat-1" />,
      );

      // Trigger interval update
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Timer should show ~2 seconds (preserved from original start)
      await waitFor(() => {
        const animatedNumber = screen.getByTestId("animated-number");
        const value = parseFloat(
          animatedNumber.getAttribute("data-value") || "0",
        );
        expect(value).toBeGreaterThanOrEqual(2);
      });

      Date.now = realDateNow;
    });

    it("should preserve timer across multiple remounts", async () => {
      const realDateNow = Date.now;
      let mockTime = 1000000;
      Date.now = jest.fn(() => mockTime);

      // First mount
      let component = render(
        <DurationDisplay duration={undefined} chatId="persistent-chat" />,
      );

      // Advance 500ms
      mockTime += 500;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Unmount and remount 3 times
      for (let i = 0; i < 3; i++) {
        component.unmount();

        // Advance time while unmounted
        mockTime += 500;

        component = render(
          <DurationDisplay duration={undefined} chatId="persistent-chat" />,
        );

        act(() => {
          jest.advanceTimersByTime(100);
        });
      }

      // Total time should be ~2 seconds (500ms initial + 3 * 500ms)
      await waitFor(() => {
        const animatedNumber = screen.getByTestId("animated-number");
        const value = parseFloat(
          animatedNumber.getAttribute("data-value") || "0",
        );
        expect(value).toBeGreaterThanOrEqual(2);
      });

      Date.now = realDateNow;
    });

    it("should start new timer if chatId changes", async () => {
      const realDateNow = Date.now;
      let mockTime = 1000000;
      Date.now = jest.fn(() => mockTime);

      const { rerender } = render(
        <DurationDisplay duration={undefined} chatId="chat-1" />,
      );

      // Advance time
      mockTime += 2000;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      await waitFor(() => {
        const animatedNumber = screen.getByTestId("animated-number");
        const value = parseFloat(
          animatedNumber.getAttribute("data-value") || "0",
        );
        expect(value).toBeGreaterThanOrEqual(2);
      });

      // Reset mock time for new chat
      mockTime = 1000000;

      // Change to different chat
      rerender(<DurationDisplay duration={undefined} chatId="chat-2" />);

      // New chat should start at 0
      act(() => {
        jest.advanceTimersByTime(100);
      });

      const animatedNumber = screen.getByTestId("animated-number");
      const value = parseFloat(
        animatedNumber.getAttribute("data-value") || "0",
      );
      expect(value).toBeLessThan(0.5);

      Date.now = realDateNow;
    });

    it("should clean up startTime when duration is finalized", async () => {
      const realDateNow = Date.now;
      let mockTime = 1000000;
      Date.now = jest.fn(() => mockTime);

      const { rerender } = render(
        <DurationDisplay duration={undefined} chatId="finalizing-chat" />,
      );

      // Advance time
      mockTime += 1500;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Finalize duration
      rerender(<DurationDisplay duration={1500} chatId="finalizing-chat" />);

      const animatedNumber = screen.getByTestId("animated-number");
      expect(animatedNumber.textContent).toBe("1.5s");

      // No loading spinner should be visible
      expect(screen.queryByTestId("loading-spinner")).not.toBeInTheDocument();

      Date.now = realDateNow;
    });

    it("should handle rapid mount/unmount cycles", async () => {
      const realDateNow = Date.now;
      let mockTime = 1000000;
      Date.now = jest.fn(() => mockTime);

      // Rapidly mount and unmount
      for (let i = 0; i < 5; i++) {
        const component = render(
          <DurationDisplay duration={undefined} chatId="rapid-chat" />,
        );

        mockTime += 100;
        act(() => {
          jest.advanceTimersByTime(100);
        });

        component.unmount();
      }

      // Final mount
      render(<DurationDisplay duration={undefined} chatId="rapid-chat" />);

      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Should show accumulated time (~500ms)
      await waitFor(() => {
        const animatedNumber = screen.getByTestId("animated-number");
        const value = parseFloat(
          animatedNumber.getAttribute("data-value") || "0",
        );
        expect(value).toBeGreaterThanOrEqual(0.5);
      });

      Date.now = realDateNow;
    });

    it("should not create duplicate intervals when remounting", () => {
      const setIntervalSpy = jest.spyOn(global, "setInterval");

      // First mount
      const { unmount } = render(
        <DurationDisplay duration={undefined} chatId="interval-chat" />,
      );

      const firstCallCount = setIntervalSpy.mock.calls.length;

      // Unmount
      unmount();

      // Remount
      render(<DurationDisplay duration={undefined} chatId="interval-chat" />);

      const secondCallCount = setIntervalSpy.mock.calls.length;

      // Should only have created one new interval on remount
      expect(secondCallCount - firstCallCount).toBe(1);

      setIntervalSpy.mockRestore();
    });
  });

  describe("timer accuracy", () => {
    it("should maintain accurate time even with delayed interval execution", async () => {
      const realDateNow = Date.now;
      let mockTime = 1000000;
      Date.now = jest.fn(() => mockTime);

      render(<DurationDisplay duration={undefined} chatId="accurate-timer" />);

      // Simulate 3 seconds passing with irregular interval updates
      mockTime += 1000;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Skip some interval ticks
      mockTime += 1500;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      mockTime += 500;
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Should show accurate total time (~3 seconds) not interval-based calculation
      await waitFor(() => {
        const animatedNumber = screen.getByTestId("animated-number");
        const value = parseFloat(
          animatedNumber.getAttribute("data-value") || "0",
        );
        expect(value).toBeGreaterThanOrEqual(2.9);
        expect(value).toBeLessThanOrEqual(3.1);
      });

      Date.now = realDateNow;
    });
  });
});
