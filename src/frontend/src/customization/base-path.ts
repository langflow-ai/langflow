export function normalizeBasePath(value: string): string {
  const path = value.trim().replace(/\/+$/, "");
  if (!path) return "";
  const prefix = path.startsWith("/") ? path : `/${path}`;
  if (
    !/^\/[a-zA-Z0-9._~/-]+$/.test(prefix) ||
    prefix
      .slice(1)
      .split("/")
      .some((part) => !part || part === "." || part === "..")
  ) {
    throw new Error(
      "The frontend base path must be a URL path such as /langflow.",
    );
  }
  return prefix;
}
