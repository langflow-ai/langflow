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

const addMemoryToCacheValue = (old: unknown, memory: MemoryInfo): unknown => {
  if (!isRecord(old)) return old;

  // InfiniteQuery shape: { pages: [{ items: [...] }, ...], pageParams: [...] }
  if (Array.isArray(old.pages)) {
    const pages = old.pages;
    if (pages.length === 0) return old;

    const alreadyPresent = pages.some(
      (page) =>
        isRecord(page) &&
        Array.isArray(page.items) &&
        page.items.some((item) => getStringId(item) === memory.id),
    );
    if (alreadyPresent) return old;

    const firstPage = pages[0];
    if (!isRecord(firstPage) || !Array.isArray(firstPage.items)) return old;

    const nextFirstItems = [memory, ...firstPage.items];
    const nextFirstTotal =
      typeof firstPage.total === "number"
        ? firstPage.total + 1
        : firstPage.total;

    const nextPages = [
      { ...firstPage, items: nextFirstItems, total: nextFirstTotal },
      ...pages.slice(1).map((page) => {
        if (!isRecord(page)) return page;
        const nextTotal =
          typeof page.total === "number" ? page.total + 1 : page.total;
        return { ...page, total: nextTotal };
      }),
    ];

    return { ...old, pages: nextPages };
  }

  // Legacy/non-infinite shape: { items: [...] }
  if (!Array.isArray(old.items)) return old;

  const alreadyPresent = old.items.some(
    (item) => getStringId(item) === memory.id,
  );
  if (alreadyPresent) return old;

  const nextItems = [memory, ...old.items];
  const nextTotal = typeof old.total === "number" ? old.total + 1 : old.total;

  return { ...old, items: nextItems, total: nextTotal };
};

const removeMemoryFromCacheValue = (
  old: unknown,
  memoryId: string,
): unknown => {
  if (!isRecord(old)) return old;

  // InfiniteQuery shape: { pages: [{ items: [...] }, ...], pageParams: [...] }
  if (Array.isArray(old.pages)) {
    const pages = old.pages;
    let removedCount = 0;

    const nextPages = pages.map((page) => {
      if (!isRecord(page)) return page;

      const items = page.items;
      if (!Array.isArray(items)) return page;

      const beforeLen = items.length;
      const nextItems = items.filter((item) => getStringId(item) !== memoryId);
      const removedInPage = beforeLen - nextItems.length;
      removedCount += removedInPage;

      const nextTotal =
        typeof page.total === "number"
          ? Math.max(0, page.total - removedInPage)
          : page.total;

      return { ...page, items: nextItems, total: nextTotal };
    });

    if (removedCount === 0) return old;
    return { ...old, pages: nextPages };
  }

  // Legacy/non-infinite shape: { items: [...] }
  if (!Array.isArray(old.items)) return old;

  const nextItems = old.items.filter((item) => getStringId(item) !== memoryId);
  const removedCount = old.items.length - nextItems.length;
  const nextTotal =
    typeof old.total === "number"
      ? Math.max(0, old.total - removedCount)
      : old.total;

  return { ...old, items: nextItems, total: nextTotal };
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

export const addMemoryToMemoriesCache = (
  queryClient: QueryClient,
  memory: MemoryInfo,
) => {
  queryClient.setQueriesData(
    {
      queryKey: ["useGetMemoriesInfinite"],
      predicate: (query) => {
        const maybeFlowId = Array.isArray(query.queryKey)
          ? query.queryKey[1]
          : undefined;
        const flowIdInKey =
          typeof maybeFlowId === "string" ? maybeFlowId : undefined;

        // Update only the relevant flow list, and any unfiltered list.
        return flowIdInKey === undefined || flowIdInKey === memory.flow_id;
      },
    },
    (old: unknown) => addMemoryToCacheValue(old, memory),
  );
};

export const removeMemoryFromMemoriesCache = (
  queryClient: QueryClient,
  memoryId: string,
) => {
  queryClient.setQueriesData(
    { queryKey: ["useGetMemoriesInfinite"] },
    (old: unknown) => removeMemoryFromCacheValue(old, memoryId),
  );
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
