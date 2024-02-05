import { useContext } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedAdminRoute = ({ children }) => {
  const { isAdmin, isAuthenticated, logout, userData, autoLogin } =
    useContext(AuthContext);

  if (!isAuthenticated) {
    logout();
  } else if ((userData && !isAdmin) || autoLogin) {
    return <Navigate to="/" replace />;
  } else {
    return children;
  }
};
