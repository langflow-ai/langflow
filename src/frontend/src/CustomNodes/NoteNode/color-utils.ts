import { COLOR_OPTIONS } from "@/constants/constants";

/**
 * Validates if a string is a valid hex color format.
 * Supports 3, 6, and 8 character hex codes (with or without alpha channel).
 *
 * @param value - The string to validate
 * @returns True if the string is a valid hex color, false otherwise
 *
 * @example
 * ```typescript
 * isHexColor("#FFF") // true
 * isHexColor("#FFFFFF") // true
 * isHexColor("#FFFFFFFF") // true
 * isHexColor("red") // false
 * isHexColor("#GGG") // false
 * ```
 */
export const isHexColor = (value: string): boolean =>
  /^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/.test(value);

/**
 * Expands 3-character hex codes to 6-character format.
 * Leaves 6 and 8 character codes unchanged.
 *
 * @param hex - The hex color string to expand
 * @returns The expanded hex color string
 *
 * @example
 * ```typescript
 * expand3("#FFF") // "#FFFFFF"
 * expand3("#ABC") // "#AABBCC"
 * expand3("#FFFFFF") // "#FFFFFF" (unchanged)
 * expand3("#FFFFFFFF") // "#FFFFFFFF" (unchanged)
 * ```
 */
const expand3 = (hex: string): string =>
  hex.length === 4
    ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`
    : hex;

/**
 * Resolves a color value to its final representation.
 * Handles both hex colors and preset color names from COLOR_OPTIONS.
 *
 * @param backgroundColor - The color value to resolve (hex, preset name, null, or undefined)
 * @returns The resolved color value or null if invalid
 *
 * @example
 * ```typescript
 * resolveColorValue("#FFF") // "#FFFFFF"
 * resolveColorValue("blue") // "hsl(var(--note-blue))" (from COLOR_OPTIONS)
 * resolveColorValue(null) // null
 * resolveColorValue("invalid") // null
 * ```
 */
export const resolveColorValue = (
  backgroundColor: string | null | undefined,
): string | null => {
  if (!backgroundColor) return null;
  if (isHexColor(backgroundColor)) return expand3(backgroundColor);
  const preset = COLOR_OPTIONS[backgroundColor as keyof typeof COLOR_OPTIONS];
  return preset ?? null;
};

/**
 * Converts a preset color name to its hex representation for native color picker.
 * Handles CSS variables by computing their actual color values in the browser.
 *
 * @param presetName - The preset color name from COLOR_OPTIONS
 * @returns The hex color value or null if not found or in SSR environment
 *
 * @example
 * ```typescript
 * getHexFromPreset("blue") // "#3B82F6" (computed from CSS variable)
 * getHexFromPreset("transparent") // null
 * getHexFromPreset("invalid") // null
 * ```
 */
export const getHexFromPreset = (presetName: string): string | null => {
  const colorValue = COLOR_OPTIONS[presetName as keyof typeof COLOR_OPTIONS];
  if (!colorValue) return null;

  // For CSS variables, create a temporary element to get computed color
  if (colorValue.startsWith("hsl(var(--note-")) {
    if (typeof window === "undefined") return "#FFFFFF";

    // Create a temporary element to get the computed color
    const tempEl = document.createElement("div");
    tempEl.style.color = colorValue;
    document.body.appendChild(tempEl);
    const computedColor = getComputedStyle(tempEl).color;
    document.body.removeChild(tempEl);

    // Convert RGB to hex
    const rgb = computedColor.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      const r = parseInt(rgb[0]).toString(16).padStart(2, "0");
      const g = parseInt(rgb[1]).toString(16).padStart(2, "0");
      const b = parseInt(rgb[2]).toString(16).padStart(2, "0");
      return `#${r}${g}${b}`;
    }
    return "#FFFFFF";
  }

  return colorValue;
};
