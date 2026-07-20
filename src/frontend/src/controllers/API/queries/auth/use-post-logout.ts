import { LANGFLOW_AUTO_LOGIN_OPTION } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import { getCookiesInstance } from "@/utils/cookie-manager";
import { getAuthCookie } from "@/utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLogout: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const cookies = getCookiesInstance();
  const logout = useAuthStore((state) => state.logout);

  async function logoutUser(): Promise<unknown> {
    // Auto-login state is per-backend runtime config, not a build-time constant.
    // Only skip the server logout when this backend actually runs in auto-login
    // mode; otherwise the HttpOnly refresh cookie survives and POST /refresh
    // silently re-authenticates the user after logout.
    const autoLogin =
      useAuthStore.getState().autoLogin === true ||
      getAuthCookie(cookies, LANGFLOW_AUTO_LOGIN_OPTION) === "auto";

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

      // Clear all React Query cache to prevent data leakage between users
      queryClient.clear();
    },
    onError: (error) => {
      console.error(error);
    },
    ...options,
    retry: false,
  });

  return mutation;
};
