import { UseMutationResult } from "@tanstack/react-query";
import { Task, useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTasksQueryParams {
  skip?: number;
  limit?: number;
}

export const useGetTasks: useMutationFunctionType<
  Task[],
  GetTasksQueryParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function getTasks({
    skip = 0,
    limit = 10,
  }: GetTasksQueryParams = {}): Promise<Task[]> {
    const res = await api.get(
      `${getURL("TASKS")}/?skip=${skip}&limit=${limit}`,
    );
    if (res.status === 200) {
      return res.data;
    }
    return [];
  }

  const mutation: UseMutationResult<Task[], any, GetTasksQueryParams> = mutate(
    ["useGetTasks"],
    getTasks,
    options,
  );

  return mutation;
};
