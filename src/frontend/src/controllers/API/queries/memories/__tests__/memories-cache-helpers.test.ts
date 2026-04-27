import { QueryClient } from "@tanstack/react-query";

import { updateMemoryInMemoriesCache } from "../memories-cache-helpers";
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
  it("updates cached items in infinite shape", () => {
    const queryClient = makeQueryClient();
    const flowAKey = ["useGetMemoriesInfinite", "flow_a"] as const;

    const target = makeMemory({ id: "target", flow_id: "flow_a", name: "old" });

    queryClient.setQueryData(flowAKey, {
      pages: [{ items: [target], total: 1 }],
      pageParams: [1],
    });

    const updated = makeMemory({ id: "target", flow_id: "flow_a", name: "new" });
    updateMemoryInMemoriesCache(queryClient, updated);

    const flowAData = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(
      queryClient,
      flowAKey,
    );
    expect(flowAData.pages[0].items[0]?.name).toBe("new");
  });

  it("updates cached items in legacy shape", () => {
    const queryClient = makeQueryClient();
    const unfilteredKey = ["useGetMemoriesInfinite", undefined] as const;

    const target = makeMemory({ id: "target", flow_id: "flow_a", name: "old" });
    queryClient.setQueryData(unfilteredKey, { items: [target], total: 1 });

    const updated = makeMemory({ id: "target", flow_id: "flow_a", name: "new" });
    updateMemoryInMemoriesCache(queryClient, updated);

    const unfilteredData = getQueryDataOrThrow<LegacyCache<MemoryInfo>>(
      queryClient,
      unfilteredKey,
    );
    expect(unfilteredData.items[0]?.name).toBe("new");
  });

  it("does not mutate cache when id does not match", () => {
    const queryClient = makeQueryClient();
    const key = ["useGetMemoriesInfinite", "flow_a"] as const;

    const existing = makeMemory({ id: "other", name: "unchanged" });
    queryClient.setQueryData(key, {
      pages: [{ items: [existing], total: 1 }],
      pageParams: [1],
    });

    updateMemoryInMemoriesCache(queryClient, makeMemory({ id: "no-match", name: "new" }));

    const data = getQueryDataOrThrow<InfiniteCache<MemoryInfo>>(queryClient, key);
    expect(data.pages[0].items[0]?.name).toBe("unchanged");
  });
});
