import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";
import useAuthStore from "@/stores/authStore";

export const ProtectedAdminRoute = ({ children }) => {
  const { isAdmin, logout, userData, autoLogin } =
    useContext(AuthContext);

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);


  if (!isAuthenticated) {
    logout();
  } else if ((userData && !isAdmin) || autoLogin) {
    return <Navigate to="/" replace />;
  } else {
    return children;
  }
};
