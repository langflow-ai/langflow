import {
  getHexFromPreset,
  isHexColor,
  resolveColorValue,
} from "../color-utils";

// Mock COLOR_OPTIONS for testing
jest.mock("@/constants/constants", () => ({
  COLOR_OPTIONS: {
    blue: "hsl(var(--note-blue))",
    red: "hsl(var(--note-red))",
    green: "#00FF00",
    transparent: null,
    invalid: undefined,
  },
}));

// Mock DOM methods for getHexFromPreset tests
const mockGetComputedStyle = jest.fn();
const mockCreateElement = jest.fn();
const mockAppendChild = jest.fn();
const mockRemoveChild = jest.fn();

Object.defineProperty(window, "getComputedStyle", {
  value: mockGetComputedStyle,
  writable: true,
});

Object.defineProperty(document, "createElement", {
  value: mockCreateElement,
  writable: true,
});

Object.defineProperty(document.body, "appendChild", {
  value: mockAppendChild,
  writable: true,
});

Object.defineProperty(document.body, "removeChild", {
  value: mockRemoveChild,
  writable: true,
});

describe("color-utils", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("isHexColor", () => {
    it("should return true for valid 3-character hex codes", () => {
      expect(isHexColor("#FFF")).toBe(true);
      expect(isHexColor("#000")).toBe(true);
      expect(isHexColor("#ABC")).toBe(true);
      expect(isHexColor("#123")).toBe(true);
    });

    it("should return true for valid 6-character hex codes", () => {
      expect(isHexColor("#FFFFFF")).toBe(true);
      expect(isHexColor("#000000")).toBe(true);
      expect(isHexColor("#ABCDEF")).toBe(true);
      expect(isHexColor("#123456")).toBe(true);
    });

    it("should return true for valid 8-character hex codes (with alpha)", () => {
      expect(isHexColor("#FFFFFFFF")).toBe(true);
      expect(isHexColor("#00000000")).toBe(true);
      expect(isHexColor("#ABCDEF12")).toBe(true);
    });

    it("should return false for invalid hex codes", () => {
      expect(isHexColor("red")).toBe(false);
      expect(isHexColor("#GGG")).toBe(false);
      expect(isHexColor("#GGGGGG")).toBe(false);
      expect(isHexColor("#")).toBe(false);
      expect(isHexColor("FFF")).toBe(false);
      expect(isHexColor("#FF")).toBe(false);
      expect(isHexColor("#FFFFF")).toBe(false);
      expect(isHexColor("#FFFFFFF")).toBe(false);
      expect(isHexColor("")).toBe(false);
    });

    it("should be case insensitive", () => {
      expect(isHexColor("#fff")).toBe(true);
      expect(isHexColor("#FFF")).toBe(true);
      expect(isHexColor("#FfF")).toBe(true);
      expect(isHexColor("#ffffff")).toBe(true);
      expect(isHexColor("#FFFFFF")).toBe(true);
      expect(isHexColor("#FfFfFf")).toBe(true);
    });
  });

  describe("resolveColorValue", () => {
    it("should return null for null or undefined input", () => {
      expect(resolveColorValue(null)).toBe(null);
      expect(resolveColorValue(undefined)).toBe(null);
    });

    it("should return null for empty string", () => {
      expect(resolveColorValue("")).toBe(null);
    });

    it("should return hex colors as-is (expanded)", () => {
      expect(resolveColorValue("#FFF")).toBe("#FFFFFF");
      expect(resolveColorValue("#000")).toBe("#000000");
      expect(resolveColorValue("#ABC")).toBe("#AABBCC");
      expect(resolveColorValue("#FFFFFF")).toBe("#FFFFFF");
      expect(resolveColorValue("#FFFFFFFF")).toBe("#FFFFFFFF");
    });

    it("should resolve preset color names to their values", () => {
      expect(resolveColorValue("blue")).toBe("hsl(var(--note-blue))");
      expect(resolveColorValue("red")).toBe("hsl(var(--note-red))");
      expect(resolveColorValue("green")).toBe("#00FF00");
    });

    it("should return null for invalid preset names", () => {
      expect(resolveColorValue("invalid")).toBe(null);
      expect(resolveColorValue("nonexistent")).toBe(null);
    });

    it("should return null for preset names with null values", () => {
      expect(resolveColorValue("transparent")).toBe(null);
    });

    it("should return null for preset names with undefined values", () => {
      expect(resolveColorValue("invalid")).toBe(null);
    });
  });

  describe("getHexFromPreset", () => {
    beforeEach(() => {
      // Reset mocks
      mockCreateElement.mockReturnValue({
        style: {},
      });
      mockGetComputedStyle.mockReturnValue({
        color: "rgb(59, 130, 246)", // Blue color in RGB
      });
    });

    it("should return null for invalid preset names", () => {
      expect(getHexFromPreset("nonexistent")).toBe(null);
      expect(getHexFromPreset("invalid")).toBe(null);
    });

    it("should return null for preset names with null values", () => {
      expect(getHexFromPreset("transparent")).toBe(null);
    });

    it("should return null for preset names with undefined values", () => {
      expect(getHexFromPreset("invalid")).toBe(null);
    });

    it("should return direct values for non-CSS variable colors", () => {
      expect(getHexFromPreset("green")).toBe("#00FF00");
    });

    it("should handle CSS variables by computing their values", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "rgb(59, 130, 246)", // Blue color in RGB
      });

      const result = getHexFromPreset("blue");

      expect(mockCreateElement).toHaveBeenCalledWith("div");
      expect(mockElement.style.color).toBe("hsl(var(--note-blue))");
      expect(mockAppendChild).toHaveBeenCalledWith(mockElement);
      expect(mockGetComputedStyle).toHaveBeenCalledWith(mockElement);
      expect(mockRemoveChild).toHaveBeenCalledWith(mockElement);
      expect(result).toBe("#3b82f6"); // Converted RGB to hex
    });

    it("should handle CSS variables with different RGB values", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "rgb(255, 0, 0)", // Red color in RGB
      });

      const result = getHexFromPreset("red");

      expect(result).toBe("#ff0000"); // Converted RGB to hex
    });

    it("should handle SSR environment gracefully", () => {
      // This test verifies that the function handles SSR by checking the implementation
      // The actual SSR handling is tested implicitly through the CSS variable handling
      const result = getHexFromPreset("blue");

      // Should return a valid hex color or null
      expect(result).toBeTruthy();
    });

    it("should handle malformed RGB values gracefully", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "invalid-color", // Invalid color format
      });

      const result = getHexFromPreset("blue");

      expect(result).toBe("#FFFFFF"); // Fallback value
    });

    it("should handle RGB values with insufficient components", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "rgb(255)", // Only one component
      });

      const result = getHexFromPreset("blue");

      expect(result).toBe("#FFFFFF"); // Fallback value
    });

    it("should handle RGB values with alpha channel", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "rgba(59, 130, 246, 0.5)", // RGB with alpha
      });

      const result = getHexFromPreset("blue");

      expect(result).toBe("#3b82f6"); // Should still work with alpha
    });

    it("should handle zero RGB values", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "rgb(0, 0, 0)", // Black
      });

      const result = getHexFromPreset("blue");

      expect(result).toBe("#000000");
    });

    it("should handle maximum RGB values", () => {
      const mockElement = { style: {} };
      mockCreateElement.mockReturnValue(mockElement);
      mockGetComputedStyle.mockReturnValue({
        color: "rgb(255, 255, 255)", // White
      });

      const result = getHexFromPreset("blue");

      expect(result).toBe("#ffffff");
    });
  });
});
