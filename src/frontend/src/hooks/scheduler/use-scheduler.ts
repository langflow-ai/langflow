import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  getSchedulers, 
  getScheduler, 
  createScheduler, 
  updateScheduler, 
  deleteScheduler,
  getSchedulerStatus,
  getNextRunTimes
} from "../../controllers/API/scheduler";
import { SchedulerCreateType, SchedulerUpdateType } from "../../types/scheduler";

export function useGetSchedulers(flowId?: string) {
  return useQuery({
    queryKey: ["schedulers", flowId],
    queryFn: () => getSchedulers(flowId),
    refetchInterval: 10000, // Refresh every 10 seconds
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
    staleTime: 5000,
  });
}

export function useGetScheduler(id: string) {
  return useQuery({
    queryKey: ["scheduler", id],
    queryFn: () => getScheduler(id),
    enabled: !!id,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });
}

export function useCreateScheduler() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduler: SchedulerCreateType) => createScheduler(scheduler),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedulers"] });
      queryClient.invalidateQueries({ queryKey: ["scheduler-status"] });
      queryClient.invalidateQueries({ queryKey: ["next-run-times"] });
    },
    retry: 2,
  });
}

export function useUpdateScheduler() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, scheduler }: { id: string; scheduler: SchedulerUpdateType }) =>
      updateScheduler(id, scheduler),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedulers"] });
      queryClient.invalidateQueries({ queryKey: ["scheduler-status"] });
      queryClient.invalidateQueries({ queryKey: ["next-run-times"] });
    },
    retry: 2,
  });
}

export function useDeleteScheduler() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteScheduler(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedulers"] });
      queryClient.invalidateQueries({ queryKey: ["scheduler-status"] });
      queryClient.invalidateQueries({ queryKey: ["next-run-times"] });
    },
    retry: 2,
  });
}

export function useGetSchedulerStatus() {
  return useQuery({
    queryKey: ["scheduler-status"],
    queryFn: () => getSchedulerStatus(),
    refetchInterval: 10000, // Refresh every 10 seconds
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
    staleTime: 5000,
  });
}

export function useGetNextRunTimes(flowId?: string) {
  return useQuery({
    queryKey: ["next-run-times", flowId],
    queryFn: () => getNextRunTimes(flowId),
    refetchInterval: 10000, // Refresh every 10 seconds
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
    staleTime: 5000,
  });
} 