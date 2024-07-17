import {
  changeUser,
  resetPasswordType,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import useAuthStore from "@/stores/authStore";

export const useLogout: useMutationFunctionType = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function logoutUser(): Promise<any> {
    const autoLogin= useAuthStore.getState().autoLogin
    if(autoLogin){
      return {}
    }
    const res = await api.patch(`${getURL("LOGOUT")}`);
    return res.data;
  }

  const mutation = mutate(
    ["useLogout"],
    logoutUser,
    options,
  );

  return mutation;
};
