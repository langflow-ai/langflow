import { renderHook } from "@testing-library/react";
import { useIsMobile } from "../use-mobile";

describe("useIsMobile", () => {
  const originalMatchMedia = window.matchMedia;

  beforeAll(() => {
    // Mock matchMedia
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: jest.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: jest.fn(),
        removeListener: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        dispatchEvent: jest.fn(),
      })),
    });
  });

  afterAll(() => {
    window.matchMedia = originalMatchMedia;
  });

  it("should cleanup event listeners properly", () => {
    const addEventListenerSpy = jest.spyOn(window, "addEventListener");
    const removeEventListenerSpy = jest.spyOn(window, "removeEventListener");
    const mockMql = {
      matches: false,
      media: "(max-width: 768px)",
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      addListener: jest.fn(),
      removeListener: jest.fn(),
      onchange: null,
      dispatchEvent: jest.fn(),
    };

    (window.matchMedia as jest.Mock).mockReturnValue(mockMql);

    const { unmount } = renderHook(() => useIsMobile());

    // Cleanup on unmount
    unmount();

    // Verify both event listeners are removed (bug fix verification)
    expect(mockMql.removeEventListener).toHaveBeenCalled();
    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      "resize",
      expect.any(Function),
    );

    addEventListenerSpy.mockRestore();
    removeEventListenerSpy.mockRestore();
  });

  it("should return boolean value", () => {
    const { result } = renderHook(() => useIsMobile());
    expect(typeof result.current).toBe("boolean");
  });

  it("should respond to mobile breakpoint", () => {
    // Mock window.innerWidth
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 500, // Mobile width
    });

    const mockMql = {
      matches: true,
      media: "(max-width: 767px)",
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      addListener: jest.fn(),
      removeListener: jest.fn(),
      onchange: null,
      dispatchEvent: jest.fn(),
    };

    (window.matchMedia as jest.Mock).mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });
});
