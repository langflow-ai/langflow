import { useContext, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";

export const ProtectedAdminRoute = ({ children }) => {
  const { isAuthenticated, logout, getAuthentication, userData } =
    useContext(AuthContext);
  useEffect(() => {
    if (!isAuthenticated && !getAuthentication()) {
      window.location.replace("/login");
      logout();
    }

    if (userData && userData?.is_superuser === false) {
      logout();
    }
  }, [isAuthenticated, getAuthentication, logout, userData]);

  if (!isAuthenticated && !getAuthentication()) {
    return <Navigate to="/login" replace />;
  }

  if (userData && userData?.is_superuser === false) {
    return <Navigate to="/login" replace />;
  }

  return children;
};
