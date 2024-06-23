import { nodeColors } from "../../utils/styleUtils";

export function getNodeOutputColors(output, data, types): string[] {
  // Helper function to get the color based on type
  const getColorByType = (type) => nodeColors[type] ?? nodeColors.unknown;

  // Try to get the color based on the selected node
  let color: string = nodeColors[output.selected];
  if (color) return [color];

  // Try to get the colors based on the output types
  let colors: string[] = output.types
    .map((type) => nodeColors[type])
    .filter((color) => color);
  if (colors.length > 0) return colors;

  // Try to get the color based on the type of the selected node
  color = nodeColors[types[output.selected]];
  if (color) return [color];

  // Try to get the colors based on the types of output
  colors = output.types
    .map((type) => getColorByType(types[type]))
    .filter((color) => color);
  if (colors.length > 0) return colors;

  // Try to get the color based on the type in data
  color = nodeColors[types[data.type]];
  if (color) return [color];

  // Default to unknown color
  return [nodeColors.unknown];
}
