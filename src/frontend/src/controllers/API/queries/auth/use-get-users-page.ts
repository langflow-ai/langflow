import { keepPreviousData } from "@tanstack/react-query";
import { Users, useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface getUsersPageQueryParams {
  skip: number;
  limit: number;
}

export const useGetUserPage: useQueryFunctionType<
  getUsersPageQueryParams,
  Users
> = ({ skip, limit }) => {
  const { query } = UseRequestProcessor();

  async function getUsersPage(): Promise<Array<Users>> {
    const res = await api.get(
      `${getURL("USERS")}/?skip=${skip}&limit=${limit}`,
    );
    if (res.status === 200) {
      return res.data;
    }
    return [];
  }

  const queryResult = query(["useGetUserPage"], getUsersPage, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
