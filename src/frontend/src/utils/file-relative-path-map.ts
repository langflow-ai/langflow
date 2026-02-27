type RelativePathMap = Record<string, string>;

const STORAGE_KEY = "lf_file_relative_path_map_v1";

function safeParse(json: string | null): RelativePathMap {
  if (!json) return {};
  try {
    const parsed = JSON.parse(json) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as RelativePathMap;
  } catch {
    return {};
  }
}

export function getRelativePathForServerPath(
  serverPath: string,
): string | undefined {
  if (typeof window === "undefined") return undefined;
  const map = safeParse(window.localStorage.getItem(STORAGE_KEY));
  return map[serverPath];
}

export function setRelativePathForServerPath(
  serverPath: string,
  relativePath: string,
): void {
  if (typeof window === "undefined") return;

  const normalizedRelativePath = relativePath.replace(/^\/+/, "");
  const current = safeParse(window.localStorage.getItem(STORAGE_KEY));

  current[serverPath] = normalizedRelativePath;

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Ignore quota and serialization issues.
  }
}
