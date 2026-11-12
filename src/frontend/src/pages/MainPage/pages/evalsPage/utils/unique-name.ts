const MAX_NAME_LENGTH = 255;

/** The file name without its extension, used as the name of a dataset imported from it. */
export function datasetNameFromFile(fileName: string): string {
  const stem = fileName.replace(/\.[^./\\]+$/, "").trim();
  return (stem || fileName).slice(0, MAX_NAME_LENGTH);
}

/** `base`, or `base 2`, `base 3`... the first one no existing name takes (compared case-insensitively). */
export function uniqueName(base: string, existing: readonly string[]): string {
  const taken = new Set(existing.map((name) => name.trim().toLowerCase()));
  if (!taken.has(base.toLowerCase())) return base;
  for (let suffix = 2; ; suffix += 1) {
    const tail = ` ${suffix}`;
    const candidate = `${base.slice(0, MAX_NAME_LENGTH - tail.length)}${tail}`;
    if (!taken.has(candidate.toLowerCase())) return candidate;
  }
}
