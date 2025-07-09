import useAuthStore from "@/stores/authStore";
import type { useMutationFunctionType } from "@/types/api";

import {
  IS_AUTO_LOGIN,
  LANGFLOW_AUTO_LOGIN_OPTION,
} from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { Cookies } from "react-cookie";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLogout: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const cookies = new Cookies();
  const logout = useAuthStore((state) => state.logout);
  const isAutoLoginEnv = IS_AUTO_LOGIN;

  async function logoutUser(): Promise<any> {
    const autoLogin =
      useAuthStore.getState().autoLogin ||
      cookies.get(LANGFLOW_AUTO_LOGIN_OPTION) === "auto" ||
      isAutoLoginEnv;

    if (autoLogin) {
      return {};
    }
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
