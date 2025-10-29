import { renderHook } from "@testing-library/react";
import { useDebounce } from "../use-debounce";

// Mock lodash debounce
jest.mock("lodash", () => ({
  debounce: jest.fn((fn, delay) => {
    let timeoutId: NodeJS.Timeout | null = null;
    const debounced = (...args: any[]) => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      timeoutId = setTimeout(() => {
        fn(...args);
      }, delay);
    };
    return debounced;
  }),
}));

describe("useDebounce", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("should return a debounced function", () => {
    const callback = jest.fn();
    const { result } = renderHook(() => useDebounce(callback, 500));

    expect(typeof result.current).toBe("function");
  });

  it("should debounce the callback execution", () => {
    const callback = jest.fn();
    const { result } = renderHook(() => useDebounce(callback, 500));

    // Call the debounced function multiple times
    result.current();
    result.current();
    result.current();

    // Callback should not have been called yet
    expect(callback).not.toHaveBeenCalled();

    // Fast-forward time
    jest.advanceTimersByTime(500);

    // Callback should be called once
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("should pass arguments to the callback", () => {
    const callback = jest.fn();
    const { result } = renderHook(() => useDebounce(callback, 500));

    result.current("arg1", "arg2", 123);

    jest.advanceTimersByTime(500);

    expect(callback).toHaveBeenCalledWith("arg1", "arg2", 123);
  });

  it("should update callback reference without creating new debounced function", () => {
    const callback1 = jest.fn();
    const callback2 = jest.fn();

    const { result, rerender } = renderHook(
      ({ cb, delay }) => useDebounce(cb, delay),
      {
        initialProps: { cb: callback1, delay: 500 },
      },
    );

    const debouncedFn1 = result.current;

    // Update callback
    rerender({ cb: callback2, delay: 500 });

    const debouncedFn2 = result.current;

    // Debounced function should remain the same (memoized)
    expect(debouncedFn1).toBe(debouncedFn2);

    // Call the debounced function
    result.current();
    jest.advanceTimersByTime(500);

    // New callback should be called
    expect(callback2).toHaveBeenCalledTimes(1);
    expect(callback1).not.toHaveBeenCalled();
  });

  it("should create new debounced function when delay changes", () => {
    const callback = jest.fn();

    const { result, rerender } = renderHook(
      ({ cb, delay }) => useDebounce(cb, delay),
      {
        initialProps: { cb: callback, delay: 500 },
      },
    );

    const debouncedFn1 = result.current;

    // Update delay
    rerender({ cb: callback, delay: 1000 });

    const debouncedFn2 = result.current;

    // Debounced function should be different
    expect(debouncedFn1).not.toBe(debouncedFn2);
  });

  it("should handle rapid calls correctly", () => {
    const callback = jest.fn();
    const { result } = renderHook(() => useDebounce(callback, 500));

    // Rapid calls
    for (let i = 0; i < 10; i++) {
      result.current(i);
      jest.advanceTimersByTime(100);
    }

    // Still shouldn't be called
    expect(callback).not.toHaveBeenCalled();

    // Wait for the full delay after the last call
    jest.advanceTimersByTime(500);

    // Should be called once with the last argument
    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith(9);
  });
});
