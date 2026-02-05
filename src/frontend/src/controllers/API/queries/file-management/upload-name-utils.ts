export const SUFFIX_COUNTER_REGEX = /^(.*) \((\d+)\)$/;

export function getUniqueFilename(
  originalName: string,
  existingNames: Set<string>,
): string {
  const lastDot = originalName.lastIndexOf(".");
  const hasExt = lastDot > 0;
  const base = hasExt ? originalName.slice(0, lastDot) : originalName;
  const ext = hasExt ? originalName.slice(lastDot) : "";

  if (!existingNames.has(originalName)) return originalName;

  let counter = 2;

  const match = base.match(SUFFIX_COUNTER_REGEX);
  let rootBase = base;
  if (match) {
    rootBase = match[1];
    const current = Number.parseInt(match[2], 10);
    if (!Number.isNaN(current) && current >= 2) {
      counter = current + 1;
    }
  }

  const MAX_TRIES = 1000;
  for (let i = 0; i < MAX_TRIES; i++) {
    const candidate = `${rootBase} (${counter})${ext}`;
    if (!existingNames.has(candidate)) return candidate;
    counter++;
  }

  return `${rootBase} (${Date.now()})${ext}`;
}
