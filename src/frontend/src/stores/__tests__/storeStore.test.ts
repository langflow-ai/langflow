import { act, renderHook } from "@testing-library/react";
import { useStoreStore } from "../storeStore";

// Mock the feature flag
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_LANGFLOW_STORE: true,
}));

// Mock the API controllers - simplified without complex async operations
const mockCheckHasStore = jest.fn();
const mockCheckHasApiKey = jest.fn();

jest.mock("../../controllers/API", () => ({
  __esModule: true,
  checkHasStore: mockCheckHasStore,
  checkHasApiKey: mockCheckHasApiKey,
}));

describe("useStoreStore", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCheckHasStore.mockResolvedValue({ enabled: true });
    mockCheckHasApiKey.mockResolvedValue({
      is_valid: false,
      has_api_key: false,
    });

    act(() => {
      useStoreStore.setState({
        hasStore: true,
        validApiKey: false,
        hasApiKey: false,
        loadingApiKey: true,
      });
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useStoreStore());

      expect(result.current.hasStore).toBe(true);
      expect(result.current.validApiKey).toBe(false);
      expect(result.current.hasApiKey).toBe(false);
      expect(result.current.loadingApiKey).toBe(true);
    });
  });

  describe("updateValidApiKey", () => {
    it("should update validApiKey to true", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        result.current.updateValidApiKey(true);
      });

      expect(result.current.validApiKey).toBe(true);
    });

    it("should update validApiKey to false", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        result.current.updateValidApiKey(true);
      });
      expect(result.current.validApiKey).toBe(true);

      act(() => {
        result.current.updateValidApiKey(false);
      });
      expect(result.current.validApiKey).toBe(false);
    });

    it("should toggle validApiKey multiple times", () => {
      const { result } = renderHook(() => useStoreStore());

      for (let i = 0; i < 5; i++) {
        act(() => {
          result.current.updateValidApiKey(i % 2 === 0);
        });
        expect(result.current.validApiKey).toBe(i % 2 === 0);
      }
    });
  });

  describe("updateLoadingApiKey", () => {
    it("should update loadingApiKey to false", () => {
      const { result } = renderHook(() => useStoreStore());
      expect(result.current.loadingApiKey).toBe(true);

      act(() => {
        result.current.updateLoadingApiKey(false);
      });

      expect(result.current.loadingApiKey).toBe(false);
    });

    it("should update loadingApiKey to true", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        result.current.updateLoadingApiKey(false);
      });
      expect(result.current.loadingApiKey).toBe(false);

      act(() => {
        result.current.updateLoadingApiKey(true);
      });
      expect(result.current.loadingApiKey).toBe(true);
    });

    it("should handle rapid loading state changes", () => {
      const { result } = renderHook(() => useStoreStore());

      const states = [false, true, false, true, false];
      states.forEach((state) => {
        act(() => {
          result.current.updateLoadingApiKey(state);
        });
        expect(result.current.loadingApiKey).toBe(state);
      });
    });
  });

  describe("updateHasApiKey", () => {
    it("should update hasApiKey to true", () => {
      const { result } = renderHook(() => useStoreStore());
      expect(result.current.hasApiKey).toBe(false);

      act(() => {
        result.current.updateHasApiKey(true);
      });

      expect(result.current.hasApiKey).toBe(true);
    });

    it("should update hasApiKey to false", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        result.current.updateHasApiKey(true);
      });
      expect(result.current.hasApiKey).toBe(true);

      act(() => {
        result.current.updateHasApiKey(false);
      });
      expect(result.current.hasApiKey).toBe(false);
    });

    it("should maintain hasApiKey state independently of other states", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        result.current.updateHasApiKey(true);
        result.current.updateValidApiKey(false);
        result.current.updateLoadingApiKey(false);
      });

      expect(result.current.hasApiKey).toBe(true);
      expect(result.current.validApiKey).toBe(false);
      expect(result.current.loadingApiKey).toBe(false);
    });
  });

  describe("state interactions", () => {
    it("should handle combined state updates correctly", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        result.current.updateValidApiKey(true);
        result.current.updateHasApiKey(true);
        result.current.updateLoadingApiKey(false);
      });

      expect(result.current.validApiKey).toBe(true);
      expect(result.current.hasApiKey).toBe(true);
      expect(result.current.loadingApiKey).toBe(false);
    });

    it("should maintain state consistency across multiple hook instances", () => {
      const { result: result1 } = renderHook(() => useStoreStore());
      const { result: result2 } = renderHook(() => useStoreStore());

      act(() => {
        result1.current.updateValidApiKey(true);
      });

      expect(result1.current.validApiKey).toBe(true);
      expect(result2.current.validApiKey).toBe(true);
    });
  });

  describe("edge cases", () => {
    it("should handle boolean state toggles", () => {
      const { result } = renderHook(() => useStoreStore());

      // Test all boolean combinations
      const combinations = [
        { valid: true, has: true, loading: true },
        { valid: false, has: true, loading: false },
        { valid: true, has: false, loading: true },
        { valid: false, has: false, loading: false },
      ];

      combinations.forEach(({ valid, has, loading }) => {
        act(() => {
          result.current.updateValidApiKey(valid);
          result.current.updateHasApiKey(has);
          result.current.updateLoadingApiKey(loading);
        });

        expect(result.current.validApiKey).toBe(valid);
        expect(result.current.hasApiKey).toBe(has);
        expect(result.current.loadingApiKey).toBe(loading);
      });
    });

    it("should handle rapid state changes", () => {
      const { result } = renderHook(() => useStoreStore());

      act(() => {
        // Rapid successive calls
        result.current.updateLoadingApiKey(true);
        result.current.updateValidApiKey(false);
        result.current.updateHasApiKey(false);
        result.current.updateValidApiKey(true);
        result.current.updateHasApiKey(true);
        result.current.updateLoadingApiKey(false);
      });

      expect(result.current.validApiKey).toBe(true);
      expect(result.current.hasApiKey).toBe(true);
      expect(result.current.loadingApiKey).toBe(false);
    });

    it("should maintain independent state for different properties", () => {
      const { result } = renderHook(() => useStoreStore());

      // Set each property independently and verify others don't change
      act(() => {
        result.current.updateValidApiKey(true);
      });
      expect(result.current.validApiKey).toBe(true);
      expect(result.current.hasApiKey).toBe(false); // Should remain unchanged
      expect(result.current.loadingApiKey).toBe(true); // Should remain unchanged

      act(() => {
        result.current.updateHasApiKey(true);
      });
      expect(result.current.validApiKey).toBe(true); // Should remain unchanged
      expect(result.current.hasApiKey).toBe(true);
      expect(result.current.loadingApiKey).toBe(true); // Should remain unchanged

      act(() => {
        result.current.updateLoadingApiKey(false);
      });
      expect(result.current.validApiKey).toBe(true); // Should remain unchanged
      expect(result.current.hasApiKey).toBe(true); // Should remain unchanged
      expect(result.current.loadingApiKey).toBe(false);
    });
  });
});
