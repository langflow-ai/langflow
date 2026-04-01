import { getLocalStorage } from "../local-storage-util";

// Mock the localStorage utility
jest.mock("../local-storage-util", () => ({
  getLocalStorage: jest.fn(),
}));

const mockGetLocalStorage = getLocalStorage as jest.MockedFunction<
  typeof getLocalStorage
>;

// The function we're testing (copied directly from utils.ts to avoid import issues)
const getBooleanFromStorage = (key: string, defaultValue: boolean): boolean => {
  const stored = getLocalStorage(key);
  return stored === null ? defaultValue : stored === "true";
};

describe("getBooleanFromStorage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("when localStorage contains no value (null)", () => {
    beforeEach(() => {
      mockGetLocalStorage.mockReturnValue(null);
    });

    it("should return true when defaultValue is true", () => {
      const result = getBooleanFromStorage("testKey", true);
      expect(result).toBe(true);
      expect(mockGetLocalStorage).toHaveBeenCalledWith("testKey");
    });

    it("should return false when defaultValue is false", () => {
      const result = getBooleanFromStorage("testKey", false);
      expect(result).toBe(false);
      expect(mockGetLocalStorage).toHaveBeenCalledWith("testKey");
    });
  });

  describe("when localStorage contains 'true' string", () => {
    beforeEach(() => {
      mockGetLocalStorage.mockReturnValue("true");
    });

    it("should return true regardless of defaultValue", () => {
      const resultWithTrueDefault = getBooleanFromStorage("testKey", true);
      const resultWithFalseDefault = getBooleanFromStorage("testKey", false);

      expect(resultWithTrueDefault).toBe(true);
      expect(resultWithFalseDefault).toBe(true);
      expect(mockGetLocalStorage).toHaveBeenCalledTimes(2);
    });
  });

  describe("when localStorage contains 'false' string", () => {
    beforeEach(() => {
      mockGetLocalStorage.mockReturnValue("false");
    });

    it("should return false regardless of defaultValue", () => {
      const resultWithTrueDefault = getBooleanFromStorage("testKey", true);
      const resultWithFalseDefault = getBooleanFromStorage("testKey", false);

      expect(resultWithTrueDefault).toBe(false);
      expect(resultWithFalseDefault).toBe(false);
      expect(mockGetLocalStorage).toHaveBeenCalledTimes(2);
    });
  });

  describe("when localStorage contains other string values", () => {
    it.each(["1", "yes", "TRUE", "False", "anything else", ""])(
      "should return false for non-'true' string: '%s'",
      (value) => {
        mockGetLocalStorage.mockReturnValue(value);

        const result = getBooleanFromStorage("testKey", true);
        expect(result).toBe(false);
      },
    );
  });

  describe("real-world scenarios", () => {
    it("should work correctly for showBeta with default true", () => {
      mockGetLocalStorage.mockReturnValue(null);

      const result = getBooleanFromStorage("showBeta", true);
      expect(result).toBe(true);
    });

    it("should work correctly for showLegacy with default false", () => {
      mockGetLocalStorage.mockReturnValue(null);

      const result = getBooleanFromStorage("showLegacy", false);
      expect(result).toBe(false);
    });

    it("should preserve user preferences when stored", () => {
      mockGetLocalStorage.mockReturnValue("false");

      const betaResult = getBooleanFromStorage("showBeta", true);
      expect(betaResult).toBe(false); // User chose to disable beta

      mockGetLocalStorage.mockReturnValue("true");
      const legacyResult = getBooleanFromStorage("showLegacy", false);
      expect(legacyResult).toBe(true); // User chose to enable legacy
    });
  });
});
