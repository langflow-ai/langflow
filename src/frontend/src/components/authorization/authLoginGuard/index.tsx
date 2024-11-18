import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";

export const ProtectedLoginRoute = ({ children }) => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (autoLogin === true) {
    return <CustomNavigate to="/" replace />;
  }

  if (isAuthenticated) {
    return <CustomNavigate to="/" replace />;
  }

  return children;
};
