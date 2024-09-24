import { Task } from "@/types/Task";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface GetTasksParams {
  skip?: number;
  limit?: number;
  refetchInterval?: number;
}

export function useGetTasks(params: GetTasksParams = {}) {
  const { skip = 0, limit = 100, refetchInterval } = params;

  return useQuery({
    queryKey: ["tasks", { skip, limit }],
    queryFn: async () => {
      const response = await api.get<Task[]>(`${getURL("TASKS")}/`, {
        params: { skip, limit },
      });
      return response.data;
    },
    refetchInterval: refetchInterval,
  });
}
