import useAuthStore from "@/stores/authStore";
import { Navigate } from "react-router-dom";

export const ProtectedLoginRoute = ({ children }) => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (autoLogin === true) {
    window.location.replace("/");
    return <Navigate to="/" replace />;
  }

  if (isAuthenticated) {
    window.location.replace("/");
    return <Navigate to="/" replace />;
  }

  return children;
};
