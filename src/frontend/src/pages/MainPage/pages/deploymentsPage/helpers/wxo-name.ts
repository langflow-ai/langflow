export function normalizeWxoName(value: string): string {
  return value.replace(/[\s-]/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
}
