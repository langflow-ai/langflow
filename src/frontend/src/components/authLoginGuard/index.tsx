import useAuthStore from "@/stores/authStore";
import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedLoginRoute = ({ children }) => {
  const { autoLogin } = useContext(AuthContext);
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
