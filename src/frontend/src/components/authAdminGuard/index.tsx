import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedAdminRoute = ({ children }) => {
  const { isAdmin, isAuthenticated, logout, userData, autoLogin } =
    useContext(AuthContext);

  if (!isAuthenticated) {
    logout().then(() => {
      return <Navigate to="/login" replace />;
    });
  }

  if ((userData && !isAdmin) || autoLogin) {
    return <Navigate to="/" replace />;
  }

  return children;
};
