export function parseContentDispositionFilename(
  header: string | null,
  fallback: string,
): string {
  if (!header) return fallback;
  const rfc5987Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (rfc5987Match?.[1]) {
    try {
      return decodeURIComponent(rfc5987Match[1].trim());
    } catch {
      // fall through to legacy filename=
    }
  }
  const legacyMatch = header.match(/filename="?([^";\n]+)"?/);
  return legacyMatch?.[1]?.trim() ?? fallback;
}
