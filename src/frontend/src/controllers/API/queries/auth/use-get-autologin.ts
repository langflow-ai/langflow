import { keepPreviousData } from "@tanstack/react-query";
import { Users, useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetAutoLogin: useQueryFunctionType<undefined, Users> = () => {
  const { query } = UseRequestProcessor();

  const getIsAutoLogin = async () => {
    const response = await api.get<Users>(`${getURL("AUTOLOGIN")}`);
    return response["data"];
  };

  const queryResult = query(["useGetAutoLogin"], getIsAutoLogin, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
