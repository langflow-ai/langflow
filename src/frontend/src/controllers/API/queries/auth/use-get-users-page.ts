import type { UseMutationResult } from "@tanstack/react-query";
import type { Users, useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface getUsersQueryParams {
  skip: number;
  limit: number;
  username?: string;
}

interface getUsersResponse {
  users: Users[];
  total_count: number;
}

export const useGetUsers: useMutationFunctionType<
  getUsersResponse,
  getUsersQueryParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function getUsers({
    skip,
    limit,
    username,
  }: getUsersQueryParams): Promise<getUsersResponse> {
    const res = await api.get(
      `${getURL("USERS")}/?skip=${skip}&limit=${limit}${
        username ? `&username=${username}` : ""
      }`,
    );
    if (res.status === 200) {
      return res.data;
    }
    return { total_count: 0, users: [] };
  }

  const mutation: UseMutationResult<
    getUsersResponse,
    Error,
    getUsersQueryParams
  > = mutate(["useGetUsers"], getUsers, options);

  return mutation;
};
