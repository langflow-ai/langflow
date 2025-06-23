import { IS_AUTO_LOGIN } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";

export const useIsAutoLogin = (): boolean => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAutoLoginEnv = IS_AUTO_LOGIN;
  return autoLogin ?? isAutoLoginEnv;
};
