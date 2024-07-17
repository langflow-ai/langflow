import useAuthStore from "@/stores/authStore";
import {
  changeUser,
  resetPasswordType,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLogout: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  async function logoutUser(): Promise<any> {
    const autoLogin = useAuthStore.getState().autoLogin;
    if (autoLogin) {
      return {};
    }
    const res = await api.patch(`${getURL("LOGOUT")}`);
    return res.data;
  }

  const mutation = mutate(["useLogout"], logoutUser, {
    onSuccess: () => {
      logout();
      navigate("/login");
    },
    onError: (error) => {
      console.error(error);
    },
    ...options,
  });

  return mutation;
};
