import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";

export const ProtectedLoginRoute = ({ children }) => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (autoLogin === true || isAuthenticated) {
    const urlParams = new URLSearchParams(window.location.search);
    const redirectPath = urlParams.get("redirect");

    if (redirectPath) {
      return <CustomNavigate to={redirectPath} replace />;
    }
    return <CustomNavigate to="/home" replace />;
  }

  return children;
};
