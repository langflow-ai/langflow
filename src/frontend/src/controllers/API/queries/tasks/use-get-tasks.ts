import { Task } from "@/types/Task";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

interface GetTasksParams {
  skip?: number;
  limit?: number;
}

export function useGetTasks(params: GetTasksParams = {}) {
  return useQuery({
    queryKey: ["tasks", params],
    queryFn: async () => {
      const { skip = 0, limit = 100 } = params;
      const response = await api.get<Task[]>(
        `/tasks?skip=${skip}&limit=${limit}`,
      );
      return response.data;
    },
  });
}
