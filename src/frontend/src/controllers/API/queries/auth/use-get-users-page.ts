import type { UseMutationResult } from "@tanstack/react-query";
import type { Users, useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface getUsersQueryParams {
  skip: number;
  limit: number;
}

export const useGetUsers: useMutationFunctionType<any, getUsersQueryParams> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  async function getUsers({
    skip,
    limit,
  }: getUsersQueryParams): Promise<Array<Users>> {
    const res = await api.get(
      `${getURL("USERS")}/?skip=${skip}&limit=${limit}`,
    );
    if (res.status === 200) {
      return res.data;
    }
    return [];
  }

  const mutation: UseMutationResult<
    getUsersQueryParams,
    any,
    getUsersQueryParams
  > = mutate(["useGetUsers"], getUsers, options);

  return mutation;
};
