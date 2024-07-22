import { LoginType, changeUser, useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useRefreshAccessToken: useMutationFunctionType<undefined, any> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  async function refreshAccess(): Promise<any> {
    const res = await api.post(`${getURL("REFRESH")}`);
    return res.data;
  }

  const mutation: UseMutationResult = mutate(
    ["useRefrshAccessToken"],
    refreshAccess,
    options,
  );

  return mutation;
};
