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

export const useGetUsers: useMutationFunctionType<
  Array<Users>,
  getUsersQueryParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function getUsers({
    skip,
    limit,
    username,
  }: getUsersQueryParams): Promise<Array<Users>> {
    const res = await api.get(
      `${getURL("USERS")}/?skip=${skip}&limit=${limit}${
        username ? `&username=${username}` : ""
      }`,
    );
    if (res.status === 200) {
      return res.data;
    }
    return [];
  }

  const mutation: UseMutationResult<
    Array<Users>,
    Error,
    getUsersQueryParams
  > = mutate(["useGetUsers"], getUsers, options);

  return mutation;
};
