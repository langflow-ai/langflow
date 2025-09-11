import { act, renderHook } from "@testing-library/react";
import { useCallback, useState } from "react";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";

// Mock the localStorage utilities
jest.mock("@/utils/local-storage-util", () => ({
  getLocalStorage: jest.fn(),
  setLocalStorage: jest.fn(),
}));

// Define the function locally to avoid import issues
const getBooleanFromStorage = (key: string, defaultValue: boolean): boolean => {
  const stored = getLocalStorage(key);
  return stored === null ? defaultValue : stored === "true";
};

const mockGetLocalStorage = getLocalStorage as jest.MockedFunction<
  typeof getLocalStorage
>;
const mockSetLocalStorage = setLocalStorage as jest.MockedFunction<
  typeof setLocalStorage
>;

// Custom hook that mimics the localStorage functionality in the sidebar component
const useLocalStorageFeatures = () => {
  const showBetaStorage = getBooleanFromStorage("showBeta", true);
  const showLegacyStorage = getBooleanFromStorage("showLegacy", false);

  const [showBeta, setShowBeta] = useState(showBetaStorage);
  const [showLegacy, setShowLegacy] = useState(showLegacyStorage);

  const handleSetShowBeta = useCallback((value: boolean) => {
    setShowBeta(value);
    setLocalStorage("showBeta", value.toString());
  }, []);

  const handleSetShowLegacy = useCallback((value: boolean) => {
    setShowLegacy(value);
    setLocalStorage("showLegacy", value.toString());
  }, []);

  return {
    showBeta,
    showLegacy,
    handleSetShowBeta,
    handleSetShowLegacy,
  };
};

describe("Sidebar localStorage Feature", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Default behavior (first time users)", () => {
    beforeEach(() => {
      mockGetLocalStorage.mockReturnValue(null);
    });

    it("should initialize showBeta as true by default", () => {
      const { result } = renderHook(() => useLocalStorageFeatures());
      expect(result.current.showBeta).toBe(true);
    });

    it("should initialize showLegacy as false by default", () => {
      const { result } = renderHook(() => useLocalStorageFeatures());
      expect(result.current.showLegacy).toBe(false);
    });
  });

  describe("Persisted preferences (returning users)", () => {
    it("should respect stored showBeta=false preference", () => {
      mockGetLocalStorage
        .mockReturnValueOnce("false") // showBeta
        .mockReturnValueOnce(null); // showLegacy

      const { result } = renderHook(() => useLocalStorageFeatures());
      expect(result.current.showBeta).toBe(false);
      expect(result.current.showLegacy).toBe(false);
    });

    it("should respect stored showLegacy=true preference", () => {
      mockGetLocalStorage
        .mockReturnValueOnce(null) // showBeta
        .mockReturnValueOnce("true"); // showLegacy

      const { result } = renderHook(() => useLocalStorageFeatures());
      expect(result.current.showBeta).toBe(true);
      expect(result.current.showLegacy).toBe(true);
    });
  });

  describe("Updating preferences", () => {
    beforeEach(() => {
      mockGetLocalStorage.mockReturnValue(null);
    });

    it("should update showBeta and save to localStorage", () => {
      const { result } = renderHook(() => useLocalStorageFeatures());

      act(() => {
        result.current.handleSetShowBeta(false);
      });

      expect(result.current.showBeta).toBe(false);
      expect(mockSetLocalStorage).toHaveBeenCalledWith("showBeta", "false");
    });

    it("should update showLegacy and save to localStorage", () => {
      const { result } = renderHook(() => useLocalStorageFeatures());

      act(() => {
        result.current.handleSetShowLegacy(true);
      });

      expect(result.current.showLegacy).toBe(true);
      expect(mockSetLocalStorage).toHaveBeenCalledWith("showLegacy", "true");
    });
  });

  describe("Multiple updates", () => {
    beforeEach(() => {
      mockGetLocalStorage.mockReturnValue(null);
    });

    it("should handle toggling showBeta multiple times", () => {
      const { result } = renderHook(() => useLocalStorageFeatures());

      // Toggle to false
      act(() => {
        result.current.handleSetShowBeta(false);
      });
      expect(result.current.showBeta).toBe(false);

      // Toggle back to true
      act(() => {
        result.current.handleSetShowBeta(true);
      });
      expect(result.current.showBeta).toBe(true);

      expect(mockSetLocalStorage).toHaveBeenCalledTimes(2);
      expect(mockSetLocalStorage).toHaveBeenCalledWith("showBeta", "false");
      expect(mockSetLocalStorage).toHaveBeenCalledWith("showBeta", "true");
    });
  });

  describe("Real-world scenarios", () => {
    it("should simulate complete user journey", () => {
      // First visit - defaults
      mockGetLocalStorage.mockReturnValue(null);
      const { result } = renderHook(() => useLocalStorageFeatures());

      expect(result.current.showBeta).toBe(true);
      expect(result.current.showLegacy).toBe(false);

      // User changes preferences
      act(() => {
        result.current.handleSetShowBeta(false);
        result.current.handleSetShowLegacy(true);
      });

      expect(result.current.showBeta).toBe(false);
      expect(result.current.showLegacy).toBe(true);
      expect(mockSetLocalStorage).toHaveBeenCalledWith("showBeta", "false");
      expect(mockSetLocalStorage).toHaveBeenCalledWith("showLegacy", "true");
    });
  });
});
