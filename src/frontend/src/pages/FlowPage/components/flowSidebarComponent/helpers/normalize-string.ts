export function normalizeString(str: string): string {
  return str.toLowerCase().replace(/_/g, " ").replace(/\s+/g, "");
}
