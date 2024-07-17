import { keepPreviousData } from "@tanstack/react-query";
import { Users, useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetUserData: useQueryFunctionType<undefined, Users> = () => {
  const { query } = UseRequestProcessor();

  const getUserData = async () => {
    const response = await api.get<Users>(`${getURL("USERS")}/whoami`);
    return response["data"];
  };

  const queryResult = query(["useGetUserData"], getUserData, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
