/** Returns the URL if its scheme is http(s), otherwise null. Guards against
 * `javascript:` / `data:` / `vbscript:` and other unsafe schemes that
 * React would otherwise pass through to a clickable anchor in production. */
export function safeUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? raw
      : null;
  } catch {
    return null;
  }
}
