import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  getSchedulers, 
  getScheduler, 
  createScheduler, 
  updateScheduler, 
  deleteScheduler 
} from "../../controllers/API/scheduler";
import { SchedulerCreateType, SchedulerUpdateType } from "../../types/scheduler";

export function useGetSchedulers(flowId?: string) {
  return useQuery({
    queryKey: ["schedulers", flowId],
    queryFn: () => getSchedulers(flowId),
  });
}

export function useGetScheduler(id: string) {
  return useQuery({
    queryKey: ["scheduler", id],
    queryFn: () => getScheduler(id),
    enabled: !!id,
  });
}

export function useCreateScheduler() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (scheduler: SchedulerCreateType) => createScheduler(scheduler),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["schedulers", variables.flow_id] });
    },
  });
}

export function useUpdateScheduler() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, scheduler }: { id: string; scheduler: SchedulerUpdateType }) => 
      updateScheduler(id, scheduler),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["scheduler", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["schedulers"] });
    },
  });
}

export function useDeleteScheduler() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => deleteScheduler(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedulers"] });
    },
  });
} 