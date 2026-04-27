import type { QueryClient } from "@tanstack/react-query";
import type { MemoryInfo } from "./types";

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null;

const getStringId = (value: unknown): string | undefined => {
  if (!isRecord(value)) return undefined;
  const id = value.id;
  return typeof id === "string" ? id : undefined;
};

const updateMemoryInCacheValue = (
  old: unknown,
  updated: MemoryInfo,
): unknown => {
  if (!isRecord(old)) return old;

  // InfiniteQuery shape: { pages: [{ items: [...] }, ...], pageParams: [...] }
  if (Array.isArray(old.pages)) {
    let changed = false;

    const nextPages = old.pages.map((page) => {
      if (!isRecord(page) || !Array.isArray(page.items)) return page;

      const nextItems = page.items.map((item) => {
        if (getStringId(item) !== updated.id) return item;
        if (!isRecord(item)) return item;
        changed = true;
        return { ...item, ...updated };
      });

      return changed ? { ...page, items: nextItems } : page;
    });

    return changed ? { ...old, pages: nextPages } : old;
  }

  // Legacy/non-infinite shape: { items: [...] }
  if (!Array.isArray(old.items)) return old;

  let changed = false;

  const nextItems = old.items.map((item) => {
    if (getStringId(item) !== updated.id) return item;
    if (!isRecord(item)) return item;
    changed = true;
    return { ...item, ...updated };
  });

  return changed ? { ...old, items: nextItems } : old;
};

export const updateMemoryInMemoriesCache = (
  queryClient: QueryClient,
  updated: MemoryInfo,
) => {
  queryClient.setQueriesData(
    { queryKey: ["useGetMemoriesInfinite"] },
    (old: unknown) => updateMemoryInCacheValue(old, updated),
  );
};
