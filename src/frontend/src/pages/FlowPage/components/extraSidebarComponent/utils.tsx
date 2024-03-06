import { PRIORITY_SIDEBAR_ORDER } from "../../../../constants/constants";

export function sortKeys(a: string, b: string) {
  // Define the order of specific keys

  const indexA = PRIORITY_SIDEBAR_ORDER.indexOf(a.toLowerCase());
  const indexB = PRIORITY_SIDEBAR_ORDER.indexOf(b.toLowerCase());

  // Check if both keys are in the predefined order
  if (indexA !== -1 && indexB !== -1) {
    return indexA - indexB;
  }

  // If only 'a' is in the predefined order, it should come first
  if (indexA !== -1) {
    return -1;
  }

  // If only 'b' is in the predefined order, it should come first
  if (indexB !== -1) {
    return 1;
  }

  // If neither 'a' nor 'b' are in the predefined order, sort them alphabetically
  return a.localeCompare(b);
}
