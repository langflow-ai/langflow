import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

interface DeleteTaskParams {
  taskId: string;
}

export function useDeleteTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId }: DeleteTaskParams) =>
      api.delete(`/tasks/${taskId}`).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
