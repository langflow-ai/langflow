import {
  type UseMutationOptions,
  type UseMutationResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { mapMemoryApiToMemoryInfo } from "./mappers";
import { addMemoryToMemoriesCache } from "./memories-cache-helpers";
import { memoriesRetryDelay } from "./memoriesQueryConfig";
import type { CreateMemoryPayload, MemoryApiDTO, MemoryInfo } from "./types";

export const useCreateMemory: useMutationFunctionType<
  undefined,
  CreateMemoryPayload,
  MemoryInfo
> = (options?) => {
  const queryClient = useQueryClient();
  const typedOptions = options as
    | Omit<
        UseMutationOptions<MemoryInfo, unknown, CreateMemoryPayload, unknown>,
        "mutationFn" | "mutationKey"
      >
    | undefined;
  const {
    onSettled: userOnSettled,
    onSuccess: userOnSuccess,
    ...restOptions
  } = typedOptions ?? {};

  const createMemoryFn = async (
    params: CreateMemoryPayload,
  ): Promise<MemoryInfo> => {
    const response = await api.post<MemoryApiDTO>(
      `${getURL("MEMORIES")}/`,
      params,
    );
    return mapMemoryApiToMemoryInfo(response.data);
  };

  const mutation: UseMutationResult<MemoryInfo, unknown, CreateMemoryPayload> =
    useMutation<MemoryInfo, unknown, CreateMemoryPayload>({
      mutationKey: ["useCreateMemory"],
      mutationFn: createMemoryFn,
      ...restOptions,
      onSuccess: (data, variables, onMutateResult, context) => {
        // Seed the details cache for immediate render.
        queryClient.setQueryData(["useGetMemory", data.id], data);

        // Patch cached lists without forcing a refetch.
        addMemoryToMemoriesCache(queryClient, data);

        userOnSuccess?.(data, variables, onMutateResult, context);
      },
      onSettled: (data, error, variables, onMutateResult, context) => {
        userOnSettled?.(data, error, variables, onMutateResult, context);
      },
      // POST is not safe to retry by default (risk of duplicates).
      retry: false,
      retryDelay: memoriesRetryDelay,
    });

  return mutation;
};
