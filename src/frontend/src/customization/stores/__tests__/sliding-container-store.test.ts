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
    // Reset window width
    window.innerWidth = mockWindowWidth;
  });

  describe("initial state", () => {
    it("should initialize with correct default state", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      expect(result.current.isOpen).toBe(false);
      expect(result.current.width).toBe(400);
      expect(result.current.isFullscreen).toBe(false);
    });
  });

  describe("isOpen state management", () => {
    it("should update isOpen state", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setIsOpen(true);
      });

      expect(result.current.isOpen).toBe(true);

      act(() => {
        result.current.setIsOpen(false);
      });

      expect(result.current.isOpen).toBe(false);
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
  });

  describe("width state management", () => {
    it("should update width state", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setWidth(500);
      });

      expect(result.current.width).toBe(500);
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

    it("should handle width within valid range", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setWidth(600);
      });

      expect(result.current.width).toBe(600);
    });

    it("should recalculate max width when window width changes", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      // Set a large width with current window size
      window.innerWidth = 2000;
      act(() => {
        result.current.setWidth(2000);
      });

      const maxWidth1 = 2000 * 0.8; // 1600px
      expect(result.current.width).toBe(maxWidth1);

      // Change window width and set a new width
      window.innerWidth = 1000;
      act(() => {
        result.current.setWidth(2000);
      });

      const maxWidth2 = 1000 * 0.8; // 800px
      expect(result.current.width).toBe(maxWidth2);
    });
  });

  describe("isFullscreen state management", () => {
    it("should update isFullscreen state", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setIsFullscreen(true);
      });

      expect(result.current.isFullscreen).toBe(true);

      act(() => {
        result.current.setIsFullscreen(false);
      });

      expect(result.current.isFullscreen).toBe(false);
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

  describe("combined state scenarios", () => {
    it("should handle opening and setting width simultaneously", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setIsOpen(true);
        result.current.setWidth(500);
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.width).toBe(500);
    });

    it("should handle fullscreen toggle while open", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setIsOpen(true);
        result.current.toggleFullscreen();
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.isFullscreen).toBe(true);
    });

    it("should maintain state consistency during rapid updates", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.toggle();
        result.current.setWidth(600);
        result.current.toggleFullscreen();
        result.current.setWidth(700);
      });

      expect(result.current.isOpen).toBe(true);
      expect(result.current.isFullscreen).toBe(true);
      expect(result.current.width).toBe(700);
    });
  });

  describe("edge cases", () => {
    it("should handle zero width gracefully", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setWidth(0);
      });

      // Should be clamped to minimum width
      expect(result.current.width).toBe(300);
    });

    it("should handle negative width gracefully", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      act(() => {
        result.current.setWidth(-100);
      });

      // Should be clamped to minimum width
      expect(result.current.width).toBe(300);
    });

    it("should handle very small window width", () => {
      const { result } = renderHook(() => useSlidingContainerStore());

      window.innerWidth = 200;
      act(() => {
        result.current.setWidth(1000);
      });

      // Max width should be 80% of 200 = 160, but min is 300
      // So it should be clamped to 300 (minimum)
      expect(result.current.width).toBe(300);
    });
  });
});
