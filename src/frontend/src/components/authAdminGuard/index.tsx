import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";
import useAuthStore from "@/stores/authStore";

export const ProtectedAdminRoute = ({ children }) => {
  const { isAdmin, isAuthenticated, logout, userData } =
    useContext(AuthContext);

  const autoLogin = useAuthStore((state) => state.autoLogin);

  if (!isAuthenticated) {
    logout();
  } else if ((userData && !isAdmin) || autoLogin) {
    return <Navigate to="/" replace />;
  } else {
    return children;
  }
};
