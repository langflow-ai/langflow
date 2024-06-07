import { priorityFields } from "../../constants/constants";

export default function sortFields(a, b, fieldOrder) {
  // Early return for empty fields
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;

  // Normalize the case to ensure case-insensitive comparison
  const normalizedFieldA = a.toLowerCase();
  const normalizedFieldB = b.toLowerCase();

  const aIsPriority = priorityFields.has(normalizedFieldA);
  const bIsPriority = priorityFields.has(normalizedFieldB);

  // Sort by priority
  if (aIsPriority && !bIsPriority) return -1;
  if (!aIsPriority && bIsPriority) return 1;

  // Check if either field is in the fieldOrder array
  const indexOfA = fieldOrder.indexOf(normalizedFieldA);
  const indexOfB = fieldOrder.indexOf(normalizedFieldB);

  // If both fields are in fieldOrder, sort by their order in the array
  if (indexOfA !== -1 && indexOfB !== -1) {
    return indexOfA - indexOfB;
  }

  // If only one of the fields is in fieldOrder, that field comes first
  if (indexOfA !== -1) {
    return -1;
  }
  if (indexOfB !== -1) {
    return 1;
  }

  // Default case for fields not in priorityFields and not found in fieldOrder
  // You might want to sort them alphabetically or in another specific manner
  return a.localeCompare(b);
}
