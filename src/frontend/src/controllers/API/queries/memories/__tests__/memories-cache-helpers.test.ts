import { QueryClient } from "@tanstack/react-query";

import {
  addMemoryToMemoriesCache,
  removeMemoryFromMemoriesCache,
  updateMemoryInMemoriesCache,
} from "../memories-cache-helpers";
import type { MemoryInfo } from "../types";

type InfiniteCache<TItem> = {
  pages: Array<{ items: TItem[]; total: number }>;
  pageParams: number[];
};

type LegacyCache<TItem> = {
  items: TItem[];
  total: number;
};

const makeMemory = (overrides: Partial<MemoryInfo> = {}): MemoryInfo => ({
  id: "mem_1",
  name: "Memory 1",
  kb_name: "kb",
  embedding_model: "model",
  embedding_provider: "provider",
  is_active: true,
  total_messages_processed: 0,
  sessions_count: 0,
  batch_size: 10,
  preprocessing_enabled: false,
  pending_messages_count: 0,
  user_id: "user_1",
  flow_id: "flow_a",
  ...overrides,
});

const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

const getQueryDataOrThrow = <T>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
): T => {
  const data = queryClient.getQueryData(queryKey);
  expect(data).toBeDefined();
  return data as unknown as T;
};

describe("memories-cache-helpers", () => {
  it("adds to the matching flow cache and the unfiltered cache", () => {
    const queryClient = makeQueryClient();

    const flowAKey = ["useGetMemoriesInfinite", "flow_a"] as const;
    const flowBKey = ["useGetMemoriesInfinite", "flow_b"] as const;
    const unfilteredKey = ["useGetMemoriesInfinite", undefined] as const;

    const existingA = makeMemory({ id: "existing_a", flow_id: "flow_a" });
    const existingB = makeMemory({ id: "existing_b", flow_id: "flow_b" });
    const newMemory = makeMemory({ id: "new_mem", flow_id: "flow_a" });

    queryClient.setQueryData(flowAKey, {
      pages: [
        { items: [existingA], total: 1 },
        { items: [], total: 1 },
      ],
      pageParams: [1, 2],
    });

    queryClient.setQueryData(flowBKey, {
      pages: [{ items: [existingB], total: 1 }],
      pageParams: [1],
    });

    queryClient.setQueryData(unfilteredKey, {
      pages: [{ items: [existingA], total: 1 }],
      pageParams: [1],
    });

    addMemoryToMemoriesCache(queryClient, newMemory);

    const flowAData = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      flowAKey,
    );
    expect(flowAData.pages[0].items[0]?.id).toBe("new_mem");
    expect(flowAData.pages[0].total).toBe(2);
    expect(flowAData.pages[1].total).toBe(2);

    const unfilteredData = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      unfilteredKey,
    );
    expect(unfilteredData.pages[0].items[0]?.id).toBe("new_mem");
    expect(unfilteredData.pages[0].total).toBe(2);

    const flowBData = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      flowBKey,
    );
    expect(flowBData.pages[0].items.map((m) => m.id)).toEqual(["existing_b"]);
  });

  it("does not insert duplicates when memory already exists in any page", () => {
    const queryClient = makeQueryClient();
    const key = ["useGetMemoriesInfinite", "flow_a"] as const;

    const existing = makeMemory({ id: "existing_a", flow_id: "flow_a" });
    const alreadyPresent = makeMemory({ id: "dup", flow_id: "flow_a" });

    queryClient.setQueryData(key, {
      pages: [
        { items: [existing], total: 2 },
        { items: [alreadyPresent], total: 2 },
      ],
      pageParams: [1, 2],
    });

    addMemoryToMemoriesCache(queryClient, alreadyPresent);

    const data = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      key,
    );
    expect(data.pages[0].items.map((m) => m.id)).toEqual(["existing_a"]);
    expect(data.pages[1].items.map((m) => m.id)).toEqual(["dup"]);
    expect(data.pages[0].total).toBe(2);
    expect(data.pages[1].total).toBe(2);
  });

  it("removes from infinite caches and adjusts totals per page", () => {
    const queryClient = makeQueryClient();
    const key = ["useGetMemoriesInfinite", "flow_a"] as const;

    const keep = makeMemory({ id: "keep", flow_id: "flow_a" });
    const toRemove = makeMemory({ id: "remove_me", flow_id: "flow_a" });

    queryClient.setQueryData(key, {
      pages: [
        { items: [keep, toRemove], total: 2 },
        { items: [toRemove], total: 2 },
      ],
      pageParams: [1, 2],
    });

    removeMemoryFromMemoriesCache(queryClient, "remove_me");

    const data = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      key,
    );
    expect(data.pages[0].items.map((m) => m.id)).toEqual(["keep"]);
    expect(data.pages[0].total).toBe(1);
    expect(data.pages[1].items).toEqual([]);
    expect(data.pages[1].total).toBe(1);
  });

  it("removes from legacy caches and adjusts totals", () => {
    const queryClient = makeQueryClient();
    const key = ["useGetMemoriesInfinite", "flow_a"] as const;

    const keep = makeMemory({ id: "keep", flow_id: "flow_a" });
    const toRemove = makeMemory({ id: "remove_me", flow_id: "flow_a" });

    queryClient.setQueryData(key, {
      items: [keep, toRemove],
      total: 2,
    });

    removeMemoryFromMemoriesCache(queryClient, "remove_me");

    const data = getQueryDataOrThrow<LegacyCache<MemoryInfo>>(queryClient, key);
    expect(data.items.map((m) => m.id)).toEqual(["keep"]);
    expect(data.total).toBe(1);
  });

  it("updates cached items in both infinite and legacy shapes", () => {
    const queryClient = makeQueryClient();

    const flowAKey = ["useGetMemoriesInfinite", "flow_a"] as const;
    const unfilteredKey = ["useGetMemoriesInfinite", undefined] as const;

    const target = makeMemory({ id: "target", flow_id: "flow_a", name: "old" });

    queryClient.setQueryData(flowAKey, {
      pages: [{ items: [target], total: 1 }],
      pageParams: [1],
    });

    // Simulate a stale/legacy cache shape that may still exist in the client.
    queryClient.setQueryData(unfilteredKey, { items: [target], total: 1 });

    const updated = makeMemory({
      id: "target",
      flow_id: "flow_a",
      name: "new",
    });
    updateMemoryInMemoriesCache(queryClient, updated);

    const flowAData = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      flowAKey,
    );
    expect(flowAData.pages[0].items[0]?.name).toBe("new");

    const unfilteredData = getQueryDataOrThrow<LegacyCache<MemoryInfo>>(
      queryClient,
      unfilteredKey,
    );
    expect(unfilteredData.items[0]?.name).toBe("new");
  });
});
