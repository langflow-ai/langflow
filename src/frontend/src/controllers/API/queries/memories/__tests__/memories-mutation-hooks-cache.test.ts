import { act, renderHook } from "@testing-library/react";

const apiPostMock = jest.fn();
const apiPatchMock = jest.fn();
const apiDeleteMock = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: (...args: unknown[]) => apiPostMock(...args),
    patch: (...args: unknown[]) => apiPatchMock(...args),
    delete: (...args: unknown[]) => apiDeleteMock(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/memories",
}));

const addMemoryToMemoriesCacheMock = jest.fn();
const removeMemoryFromMemoriesCacheMock = jest.fn();
const updateMemoryInMemoriesCacheMock = jest.fn();

jest.mock("../memories-cache-helpers", () => ({
  addMemoryToMemoriesCache: (...args: unknown[]) =>
    addMemoryToMemoriesCacheMock(...args),
  removeMemoryFromMemoriesCache: (...args: unknown[]) =>
    removeMemoryFromMemoriesCacheMock(...args),
  updateMemoryInMemoriesCache: (...args: unknown[]) =>
    updateMemoryInMemoriesCacheMock(...args),
}));

type QueryClientStub = {
  setQueryData: (queryKey: readonly unknown[], data: unknown) => void;
  cancelQueries: (filter: { queryKey: readonly unknown[] }) => Promise<void>;
  removeQueries: (filter: { queryKey: readonly unknown[] }) => void;
};

let queryClient: QueryClientStub;

type AnyMutationOptions = {
  mutationFn: (variables: unknown) => Promise<unknown>;
  onSuccess?: (
    data: unknown,
    variables: unknown,
    onMutateResult: unknown,
    context: unknown,
  ) => void;
  onSettled?: (
    data: unknown,
    error: unknown,
    variables: unknown,
    onMutateResult: unknown,
    context: unknown,
  ) => void;
};

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => queryClient,
  useMutation: (options: AnyMutationOptions) => {
    return {
      mutateAsync: async (variables: unknown) => {
        const data = await options.mutationFn(variables);

        const context = { client: queryClient };
        const onMutateResult = undefined;

        options.onSuccess?.(data, variables, onMutateResult, context);
        options.onSettled?.(data, null, variables, onMutateResult, context);

        return data;
      },
    };
  },
}));

import { mapMemoryApiToMemoryInfo } from "../mappers";
import type { MemoryApiDTO } from "../types";
import { useCreateMemory } from "../use-create-memory";
import { useDeleteMemory } from "../use-delete-memory";
import { useUpdateMemory } from "../use-update-memory";

describe("memories mutation hooks cache wiring", () => {
  const buildMemoryDto = (overrides?: Partial<MemoryApiDTO>): MemoryApiDTO => ({
    id: "m-new",
    name: "New Memory",
    flow_id: "flow-1",
    user_id: "u1",
    threshold: 1,
    auto_capture: true,
    embedding_model: "text-embedding-3-small",
    preprocessing: false,
    kb_name: "kb-1",
    created_at: "2026-04-08T00:00:00.000Z",
    ...overrides,
  });

  beforeEach(() => {
    queryClient = {
      setQueryData: jest.fn(),
      cancelQueries: jest.fn().mockResolvedValue(undefined),
      removeQueries: jest.fn(),
    };
    jest.clearAllMocks();
  });

  it("useCreateMemory seeds details cache and inserts into memories list cache", async () => {
    const dto = buildMemoryDto({
      id: "m3",
      flow_id: "flow-1",
      auto_capture: false,
    });
    apiPostMock.mockResolvedValueOnce({ data: dto });

    const { result } = renderHook(() => useCreateMemory());

    await act(async () => {
      await result.current.mutateAsync({
        name: "New Memory",
        flow_id: "flow-1",
        embedding_model: "text-embedding-3-small",
      });
    });

    const created = mapMemoryApiToMemoryInfo(dto);

    expect(queryClient.setQueryData).toHaveBeenCalledWith(
      ["useGetMemory", "m3"],
      created,
    );
    expect(addMemoryToMemoriesCacheMock).toHaveBeenCalledWith(
      queryClient,
      created,
    );
  });

  it("useDeleteMemory removes details cache and removes from memories list cache", async () => {
    apiDeleteMock.mockResolvedValueOnce({});

    const dto = buildMemoryDto({ id: "m1", flow_id: "flow-1" });
    const _memory = mapMemoryApiToMemoryInfo(dto);

    const { result } = renderHook(() => useDeleteMemory());

    await act(async () => {
      await result.current.mutateAsync({ memoryId: "m1" });
    });

    expect(queryClient.cancelQueries).toHaveBeenCalledWith({
      queryKey: ["useGetMemory", "m1"],
    });
    expect(queryClient.removeQueries).toHaveBeenCalledWith({
      queryKey: ["useGetMemory", "m1"],
    });
    expect(removeMemoryFromMemoriesCacheMock).toHaveBeenCalledWith(
      queryClient,
      "m1",
    );
  });

  it("useUpdateMemory patches details cache and updates item in memories list cache", async () => {
    const afterDto = buildMemoryDto({
      id: "m1",
      flow_id: "flow-1",
      name: "Updated Name",
      auto_capture: false,
    });
    apiPatchMock.mockResolvedValueOnce({ data: afterDto });

    const { result } = renderHook(() => useUpdateMemory());

    await act(async () => {
      await result.current.mutateAsync({ memoryId: "m1", auto_capture: false });
    });

    const updated = mapMemoryApiToMemoryInfo(afterDto);

    expect(queryClient.setQueryData).toHaveBeenCalledWith(
      ["useGetMemory", "m1"],
      updated,
    );
    expect(updateMemoryInMemoriesCacheMock).toHaveBeenCalledWith(
      queryClient,
      updated,
    );
  });
});
