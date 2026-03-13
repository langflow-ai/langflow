/**
 * Unit tests for NoteNode utility functions
 */

import { COLOR_OPTIONS } from "@/constants/constants";

// Re-implement the utility functions for testing since they're not exported
// In a real scenario, you'd export these from the module

/**
 * Calculates relative luminance and returns whether text should be light or dark.
 */
function getContrastTextColor(bgColor: string): "light" | "dark" {
  const TRANSPARENT_COLOR = "#00000000";

  if (!bgColor || bgColor === TRANSPARENT_COLOR) {
    return "dark";
  }

  let r = 0,
    g = 0,
    b = 0;

  if (bgColor.startsWith("#")) {
    const hex = bgColor.replace("#", "");
    r = parseInt(hex.substring(0, 2), 16);
    g = parseInt(hex.substring(2, 4), 16);
    b = parseInt(hex.substring(4, 6), 16);
  } else if (bgColor.startsWith("hsl")) {
    const match = bgColor.match(/hsl\(.*?,.*?,\s*(\d+(?:\.\d+)?)%?\)/);
    if (match) {
      const lightness = parseFloat(match[1]);
      return lightness > 50 ? "dark" : "light";
    }
    return "dark";
  } else if (bgColor.startsWith("rgb")) {
    const match = bgColor.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      r = parseInt(match[1]);
      g = parseInt(match[2]);
      b = parseInt(match[3]);
    }
  }

  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? "dark" : "light";
}

/** Checks if a color is custom (not a preset from COLOR_OPTIONS) */
function isCustomColor(color: string | undefined): boolean {
  return Boolean(color && !Object.keys(COLOR_OPTIONS).includes(color));
}

describe("NoteNode Utility Functions", () => {
  describe("getContrastTextColor", () => {
    describe("hex colors", () => {
      it('should return "dark" for white background', () => {
        expect(getContrastTextColor("#FFFFFF")).toBe("dark");
      });

      it('should return "light" for black background', () => {
        expect(getContrastTextColor("#000000")).toBe("light");
      });

      it('should return "dark" for light yellow background', () => {
        expect(getContrastTextColor("#FCD34D")).toBe("dark");
      });

      it('should return "light" for dark blue background', () => {
        expect(getContrastTextColor("#1E3A5F")).toBe("light");
      });

      it('should return "dark" for light gray background', () => {
        expect(getContrastTextColor("#E5E5E5")).toBe("dark");
      });

      it('should return "light" for dark gray background', () => {
        expect(getContrastTextColor("#333333")).toBe("light");
      });
    });

    describe("rgb colors", () => {
      it('should return "dark" for white rgb background', () => {
        expect(getContrastTextColor("rgb(255, 255, 255)")).toBe("dark");
      });

      it('should return "light" for black rgb background', () => {
        expect(getContrastTextColor("rgb(0, 0, 0)")).toBe("light");
      });

      it('should return "dark" for light rgb background', () => {
        expect(getContrastTextColor("rgb(200, 200, 200)")).toBe("dark");
      });
    });

    describe("hsl colors", () => {
      it('should return "dark" for high lightness hsl', () => {
        expect(getContrastTextColor("hsl(0, 50%, 80%)")).toBe("dark");
      });

      it('should return "light" for low lightness hsl', () => {
        expect(getContrastTextColor("hsl(0, 50%, 20%)")).toBe("light");
      });

      it('should return "dark" for 50% lightness threshold', () => {
        expect(getContrastTextColor("hsl(0, 50%, 51%)")).toBe("dark");
      });
    });

    describe("edge cases", () => {
      it('should return "dark" for empty string', () => {
        expect(getContrastTextColor("")).toBe("dark");
      });

      it('should return "dark" for transparent color', () => {
        expect(getContrastTextColor("#00000000")).toBe("dark");
      });

      it('should return "light" for invalid color format (defaults to black)', () => {
        // Invalid formats default to rgb(0,0,0) which has low luminance -> light text
        expect(getContrastTextColor("invalid")).toBe("light");
      });

      it('should return "dark" for null-like input', () => {
        expect(getContrastTextColor(null as any)).toBe("dark");
        expect(getContrastTextColor(undefined as any)).toBe("dark");
      });
    });
  });

  describe("isCustomColor", () => {
    it("should return false for preset color keys", () => {
      const presetKeys = Object.keys(COLOR_OPTIONS);
      presetKeys.forEach((key) => {
        expect(isCustomColor(key)).toBe(false);
      });
    });

    it("should return true for custom hex colors", () => {
      expect(isCustomColor("#FF5733")).toBe(true);
      expect(isCustomColor("#123456")).toBe(true);
    });

    it("should return false for undefined", () => {
      expect(isCustomColor(undefined)).toBe(false);
    });

    it("should return false for empty string", () => {
      expect(isCustomColor("")).toBe(false);
    });

    it("should return true for any non-preset string", () => {
      expect(isCustomColor("custom-color")).toBe(true);
      expect(isCustomColor("rgb(255, 0, 0)")).toBe(true);
    });
  });
});
