import {
  IS_AUTO_LOGIN,
  LANGFLOW_AUTO_LOGIN_OPTION,
} from "@/constants/constants";
import { useMutationFunctionType } from "@/types/api";
import { useClerk } from "@clerk/clerk-react";

import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";

import { Cookies } from "react-cookie";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const CLERK_AUTH_ENABLED = import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";

export const useLogout: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const cookies = new Cookies();
  const logout = useAuthStore((state) => state.logout);
  const isAutoLoginEnv = IS_AUTO_LOGIN;

  const { signOut } = useClerk();

  async function logoutUser(): Promise<any> {
    if (CLERK_AUTH_ENABLED) {
      await signOut(); // this redirects and clears session
      return;
    }

    const autoLogin =
      useAuthStore.getState().autoLogin ||
      cookies.get(LANGFLOW_AUTO_LOGIN_OPTION) === "auto" ||
      isAutoLoginEnv;

    if (autoLogin) return;

    const res = await api.post(`${getURL("LOGOUT")}`);
    return res.data;
  }

  const mutation = mutate(["useLogout"], logoutUser, {
    onSuccess: () => {
      logout();

      useFlowStore.getState().resetFlowState();
      useFlowsManagerStore.getState().resetStore();
      useFolderStore.getState().resetStore();

      queryClient.invalidateQueries({ queryKey: ["useGetRefreshFlowsQuery"] });
      queryClient.invalidateQueries({ queryKey: ["useGetFolders"] });
      queryClient.invalidateQueries({ queryKey: ["useGetFolder"] });
    },
    onError: (error) => {
      console.error(error);
    },
    ...options,
  });

  return mutation;
};
