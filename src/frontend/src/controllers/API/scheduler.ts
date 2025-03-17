import { SchedulerCreateType, SchedulerType, SchedulerUpdateType } from "../../types/scheduler";

export async function getSchedulers(flowId?: string): Promise<SchedulerType[]> {
  const url = flowId
    ? `/api/v1/schedulers?flow_id=${flowId}`
    : `/api/v1/schedulers`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to get schedulers");
  }
  return await response.json();
}

export async function getScheduler(id: string): Promise<SchedulerType> {
  const response = await fetch(`/api/v1/schedulers/${id}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to get scheduler");
  }
  return await response.json();
}

export async function createScheduler(
  scheduler: SchedulerCreateType
): Promise<SchedulerType> {
  const response = await fetch(`/api/v1/schedulers/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(scheduler),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to create scheduler");
  }
  return await response.json();
}

export async function updateScheduler(
  id: string,
  scheduler: SchedulerUpdateType
): Promise<SchedulerType> {
  const response = await fetch(`/api/v1/schedulers/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(scheduler),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to update scheduler");
  }
  return await response.json();
}

export async function deleteScheduler(id: string): Promise<void> {
  const response = await fetch(`/api/v1/schedulers/${id}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to delete scheduler");
  }
} 