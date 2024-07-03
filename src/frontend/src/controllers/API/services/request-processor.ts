import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QueryFunctionType } from "../../../types/api";

export function UseRequestProcessor(): {query:QueryFunctionType, mutate: any} {
  const queryClient = useQueryClient();

  function query(queryKey, queryFn, options = {}) {
    return useQuery({
      queryKey,
      queryFn,
      ...options,
    });
  }

  function mutate(mutationKey: any, mutationFn: any, options = {}): any {
    return useMutation({
      mutationKey,
      mutationFn,
      onSettled: () => queryClient.invalidateQueries(mutationKey),
      ...options,
    });
  }

  return { query, mutate };
}
