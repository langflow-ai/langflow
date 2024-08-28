import { ENABLE_PROFILE_ICONS } from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import { useStoreStore } from "@/stores/storeStore";
import { Navigate } from "react-router-dom";

export const AuthSettingsGuard = ({ children }) => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const hasStore = useStoreStore((state) => state.hasStore);

  // Hides the General settings if there is nothing to show
  const showGeneralSettings = ENABLE_PROFILE_ICONS || hasStore || !autoLogin;

  if (showGeneralSettings) {
    return children;
  } else {
    return <Navigate replace to="global-variables" />;
  }
};
