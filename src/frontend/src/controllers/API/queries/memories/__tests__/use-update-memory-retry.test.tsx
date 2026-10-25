import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import type { MemoryApiDTO } from "../types";
import { useUpdateMemory } from "../use-update-memory";

const mockPatch = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { patch: (...args: unknown[]) => mockPatch(...args) },
}));

const pauseRefusal = {
  isAxiosError: true,
  response: {
    status: 503,
    data: { detail: "This instance is being migrated." },
  },
};
const unavailable = {
  isAxiosError: true,
  response: { status: 503, data: { detail: "Temporarily unavailable" } },
};
const updatedMemory: MemoryApiDTO = {
  id: "memory-1",
  name: "Memory",
  flow_id: "flow-1",
  user_id: "user-1",
  threshold: 1,
  auto_capture: false,
  embedding_model: "text-embedding-3-small",
  preprocessing: false,
  kb_name: "memory-kb",
  created_at: "2026-10-15T00:00:00Z",
};
let client: QueryClient;

function wrapper({ children }: PropsWithChildren) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  client = new QueryClient({
    defaultOptions: { mutations: { gcTime: 0 } },
  });
  mockPatch.mockReset();
});

afterEach(() => client.clear());

it("reports a paused memory update after one request", async () => {
  mockPatch.mockRejectedValue(pauseRefusal);
  const onError = jest.fn();
  const onSettled = jest.fn();
  const { result } = renderHook(
    () => useUpdateMemory({ retryDelay: 0, onError, onSettled }),
    { wrapper },
  );

  await act(async () => {
    await expect(
      result.current.mutateAsync({ memoryId: "memory-1", auto_capture: false }),
    ).rejects.toBe(pauseRefusal);
  });

  expect(mockPatch).toHaveBeenCalledTimes(1);
  expect(onError).toHaveBeenCalledTimes(1);
  expect(onSettled).toHaveBeenCalledTimes(1);
  expect(client.getQueryData(["useGetMemory", "memory-1"])).toBeUndefined();
});

it("still retries other 503 responses and updates the cache after recovery", async () => {
  mockPatch
    .mockRejectedValueOnce(unavailable)
    .mockRejectedValueOnce(unavailable)
    .mockResolvedValueOnce({ data: updatedMemory });
  const { result } = renderHook(() => useUpdateMemory({ retryDelay: 0 }), {
    wrapper,
  });

  await act(async () => {
    await result.current.mutateAsync({
      memoryId: "memory-1",
      auto_capture: false,
    });
  });

  expect(mockPatch).toHaveBeenCalledTimes(3);
  expect(client.getQueryData(["useGetMemory", "memory-1"])).toMatchObject({
    id: "memory-1",
    is_active: false,
  });
});

it("keeps the two-retry limit for other failures", async () => {
  mockPatch.mockRejectedValue(unavailable);
  const { result } = renderHook(() => useUpdateMemory({ retryDelay: 0 }), {
    wrapper,
  });

  await act(async () => {
    await expect(
      result.current.mutateAsync({ memoryId: "memory-1", auto_capture: false }),
    ).rejects.toBe(unavailable);
  });

  expect(mockPatch).toHaveBeenCalledTimes(3);
});
