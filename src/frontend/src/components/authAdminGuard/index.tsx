import { useContext, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedAdminRoute = ({ children }) => {
  const {
    isAdmin,
    isAuthenticated,
    logout,
    getAuthentication,
    userData,
    autoLogin,
  } = useContext(AuthContext);
  useEffect(() => {
    if (!isAuthenticated && !getAuthentication()) {
      window.location.replace("/login");
      logout();
    }
  }, [isAuthenticated, getAuthentication, logout, userData]);

  if (!isAuthenticated && !getAuthentication()) {
    return <Navigate to="/login" replace />;
  }

  if ((userData && !isAdmin) || autoLogin) {
    return <Navigate to="/" replace />;
  }

  return children;
};
