import {
  changeUser,
  resetPasswordType,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface resetPasswordParams {
  user_id: string;
  password: resetPasswordType;
}

export const useResetPassword: useMutationFunctionType<
  undefined,
  resetPasswordParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function resetPassword({
    user_id,
    password,
  }: resetPasswordParams): Promise<any> {
    const res = await api.patch(
      `${getURL("USERS")}/${user_id}/reset-password`,
      password,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    resetPasswordParams,
    any,
    resetPasswordParams
  > = mutate(["useResetPassword"], resetPassword, options);

  return mutation;
};
