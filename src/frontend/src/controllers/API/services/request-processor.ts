import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function UseRequestProcessor(): any {
  const queryClient = useQueryClient();

  function query(key: any, queryFunction: any, options = {}) {
    return useQuery({
      queryKey: key,
      queryFn: queryFunction,
      ...options,
    });
  }

  function mutate(key: any, mutationFunction: any, options = {}): any {
    return useMutation({
      mutationKey: key,
      mutationFn: mutationFunction,
      onSettled: () => queryClient.invalidateQueries(key),
      ...options,
    });
  }

  return { query, mutate };
}
