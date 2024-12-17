import sortFields from "../utils/sort-fields";

export const sortToolModeFields = (
  a: string,
  b: string,
  template: any,
  fieldOrder: string[],
  isToolMode: boolean,
) => {
  if (!isToolMode) return sortFields(a, b, fieldOrder);

  const aToolMode = template[a]?.tool_mode ?? false;
  const bToolMode = template[b]?.tool_mode ?? false;

  // If one is tool_mode and the other isn't, tool_mode goes last
  if (aToolMode && !bToolMode) return 1;
  if (!aToolMode && bToolMode) return -1;

  // If both are tool_mode or both aren't, use regular field order
  return sortFields(a, b, fieldOrder);
};
