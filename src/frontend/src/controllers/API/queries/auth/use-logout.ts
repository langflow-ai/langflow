import {
  changeUser,
  resetPasswordType,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLogout: useMutationFunctionType<undefined> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function logoutUser(): Promise<any> {
    const res = await api.patch(`${getURL("LOGOUT")}`);
    return res.data;
  }

  const mutation: UseMutationResult<undefined, any, undefined> = mutate(
    ["useLogout"],
    logoutUser,
    options,
  );

  return mutation;
};
