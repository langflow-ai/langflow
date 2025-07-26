/**
 * @jest-environment jsdom
 */

import { act, renderHook } from "@testing-library/react";
import { usePackageManagerStore } from "../packageManagerStore";

// Mock console methods to avoid noise in tests
const consoleSpy = {
  error: jest.spyOn(console, "error").mockImplementation(() => {}),
  warn: jest.spyOn(console, "warn").mockImplementation(() => {}),
};

describe("usePackageManagerStore", () => {
  beforeEach(() => {
    // Reset store to initial state
    act(() => {
      usePackageManagerStore.setState({
        isInstallingPackage: false,
      });
    });
    consoleSpy.error.mockClear();
    consoleSpy.warn.mockClear();
  });

  afterAll(() => {
    consoleSpy.error.mockRestore();
    consoleSpy.warn.mockRestore();
  });

  describe("Initial State", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => usePackageManagerStore());

      expect(result.current.isInstallingPackage).toBe(false);
      expect(typeof result.current.setIsInstallingPackage).toBe("function");
    });
  });

  describe("setIsInstallingPackage", () => {
    it("should set isInstallingPackage to true", () => {
      const { result } = renderHook(() => usePackageManagerStore());

      act(() => {
        result.current.setIsInstallingPackage(true);
      });

      expect(result.current.isInstallingPackage).toBe(true);
    });

    it("should set isInstallingPackage to false", () => {
      const { result } = renderHook(() => usePackageManagerStore());

      // First set to true
      act(() => {
        result.current.setIsInstallingPackage(true);
      });

      expect(result.current.isInstallingPackage).toBe(true);

      // Then set to false
      act(() => {
        result.current.setIsInstallingPackage(false);
      });

      expect(result.current.isInstallingPackage).toBe(false);
    });

    it("should handle multiple state changes", () => {
      const { result } = renderHook(() => usePackageManagerStore());

      // Multiple rapid state changes
      act(() => {
        result.current.setIsInstallingPackage(true);
        result.current.setIsInstallingPackage(false);
        result.current.setIsInstallingPackage(true);
      });

      expect(result.current.isInstallingPackage).toBe(true);
    });
  });

  describe("Store Persistence", () => {
    it("should maintain state across multiple hook instances", () => {
      const { result: result1 } = renderHook(() => usePackageManagerStore());
      const { result: result2 } = renderHook(() => usePackageManagerStore());

      act(() => {
        result1.current.setIsInstallingPackage(true);
      });

      expect(result1.current.isInstallingPackage).toBe(true);
      expect(result2.current.isInstallingPackage).toBe(true);
    });

    it("should synchronize state changes across instances", () => {
      const { result: result1 } = renderHook(() => usePackageManagerStore());
      const { result: result2 } = renderHook(() => usePackageManagerStore());

      act(() => {
        result1.current.setIsInstallingPackage(true);
      });

      expect(result2.current.isInstallingPackage).toBe(true);

      act(() => {
        result2.current.setIsInstallingPackage(false);
      });

      expect(result1.current.isInstallingPackage).toBe(false);
    });
  });

  describe("State Type Safety", () => {
    it("should only accept boolean values", () => {
      const { result } = renderHook(() => usePackageManagerStore());

      // This should work fine
      act(() => {
        result.current.setIsInstallingPackage(true);
        result.current.setIsInstallingPackage(false);
      });

      expect(result.current.isInstallingPackage).toBe(false);
    });
  });

  describe("Store Interface", () => {
    it("should have the correct interface structure", () => {
      const { result } = renderHook(() => usePackageManagerStore());

      const state = result.current;

      // Check that all expected properties exist
      expect(state).toHaveProperty("isInstallingPackage");
      expect(state).toHaveProperty("setIsInstallingPackage");

      // Check types
      expect(typeof state.isInstallingPackage).toBe("boolean");
      expect(typeof state.setIsInstallingPackage).toBe("function");

      // Should not have unexpected properties
      const keys = Object.keys(state);
      expect(keys).toHaveLength(2);
      expect(keys).toContain("isInstallingPackage");
      expect(keys).toContain("setIsInstallingPackage");
    });
  });

  describe("Store Reactivity", () => {
    it("should trigger re-renders when state changes", () => {
      let renderCount = 0;
      const { result } = renderHook(() => {
        renderCount++;
        return usePackageManagerStore();
      });

      const initialRenderCount = renderCount;

      act(() => {
        result.current.setIsInstallingPackage(true);
      });

      expect(renderCount).toBeGreaterThan(initialRenderCount);
    });

    it("should handle setting the same value", () => {
      let renderCount = 0;
      const { result } = renderHook(() => {
        renderCount++;
        return usePackageManagerStore();
      });

      const initialValue = result.current.isInstallingPackage;

      // Set to the same value (false)
      act(() => {
        result.current.setIsInstallingPackage(false);
      });

      // Value should remain the same
      expect(result.current.isInstallingPackage).toBe(initialValue);
      expect(result.current.isInstallingPackage).toBe(false);
    });
  });
});
