import { Task } from "@/types/Task";
import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostTask: useMutationFunctionType<Task, Partial<Task>> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  async function postTask(taskData: Partial<Task>): Promise<Task> {
    const res = await api.post(getURL("TASKS"), taskData);
    if (res.status === 201) {
      return res.data;
    }
    throw new Error("Failed to create task");
  }

  const mutation: UseMutationResult<Task, any, Partial<Task>> = mutate(
    ["usePostTask"],
    postTask,
    options,
  );

  return mutation;
};
