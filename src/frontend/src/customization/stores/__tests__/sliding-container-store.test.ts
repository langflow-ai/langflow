import { act, renderHook } from "@testing-library/react";
import { useSlidingContainerStore } from "../sliding-container-store";

// Mock window.innerWidth for width calculations
const mockWindowWidth = 1200;
Object.defineProperty(window, "innerWidth", {
  writable: true,
  configurable: true,
  value: mockWindowWidth,
});

describe("useSlidingContainerStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useSlidingContainerStore.setState({
      isOpen: false,
      width: 400,
      isFullscreen: false,
    });
    window.innerWidth = mockWindowWidth;
  });

  it("should initialize with correct default state", () => {
    const { result } = renderHook(() => useSlidingContainerStore());

    expect(result.current.isOpen).toBe(false);
    expect(result.current.width).toBe(400);
    expect(result.current.isFullscreen).toBe(false);
  });

  it("should toggle isOpen state", () => {
    const { result } = renderHook(() => useSlidingContainerStore());

    expect(result.current.isOpen).toBe(false);

    act(() => {
      result.current.toggle();
    });

    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.toggle();
    });

    expect(result.current.isOpen).toBe(false);
  });

  it("should enforce minimum width (300px)", () => {
    const { result } = renderHook(() => useSlidingContainerStore());

    act(() => {
      result.current.setWidth(100);
    });

    expect(result.current.width).toBe(300);
  });

  it("should enforce maximum width (80% of window width)", () => {
    const { result } = renderHook(() => useSlidingContainerStore());
    const maxWidth = mockWindowWidth * 0.8; // 960px

    act(() => {
      result.current.setWidth(2000);
    });

    expect(result.current.width).toBe(maxWidth);
  });

  it("should toggle isFullscreen state", () => {
    const { result } = renderHook(() => useSlidingContainerStore());

    expect(result.current.isFullscreen).toBe(false);

    act(() => {
      result.current.toggleFullscreen();
    });

    expect(result.current.isFullscreen).toBe(true);

    act(() => {
      result.current.toggleFullscreen();
    });

    expect(result.current.isFullscreen).toBe(false);
  });
});
