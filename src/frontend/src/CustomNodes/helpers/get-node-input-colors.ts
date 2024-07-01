import { nodeColors } from "../../utils/styleUtils";

export function getNodeInputColors(
  input_types: string[] | undefined,
  type: string | undefined,
  types: { [char: string]: string },
) {
  // Helper function to get the color based on type
  const getColorByType = (type) => nodeColors[type] ?? nodeColors.unknown;

  // If input_types is not null and has elements, map colors based on input_types
  if (input_types && input_types.length > 0) {
    // Map through input_types and get colors from nodeColors
    const colorsFromInputs = input_types
      .map((input) => nodeColors[input])
      .filter((color) => color);
    if (colorsFromInputs.length > 0) {
      return colorsFromInputs;
    }

    // If no valid colors found in the previous step, map colors based on types[nodeColors[input]]
    const colorsFromInputTypes = input_types
      .map((input) => getColorByType(types[input]))
      .filter((color) => color);
    if (colorsFromInputTypes.length > 0) {
      return colorsFromInputTypes;
    }
  }

  // If input_types is null or empty, use the fallback logic
  const fallbackColors = [getColorByType(type)];
  if (fallbackColors.length > 0) {
    return fallbackColors;
  }

  // Default to unknown color
  return [nodeColors.unknown];
}
