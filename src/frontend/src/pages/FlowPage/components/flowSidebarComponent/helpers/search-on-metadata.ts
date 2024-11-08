import { normalizeString } from "./normalize-string";

export function searchInMetadata(metadata: any, searchTerm: string): boolean {
  if (!metadata || typeof metadata !== "object") return false;

  return Object.entries(metadata).some(([key, value]) => {
    if (typeof value === "string") {
      return (
        normalizeString(key).includes(searchTerm) ||
        normalizeString(value).includes(searchTerm)
      );
    }
    if (typeof value === "object") {
      return searchInMetadata(value, searchTerm);
    }
    return false;
  });
}
